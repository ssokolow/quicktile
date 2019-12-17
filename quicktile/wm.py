"""Wrapper around libwnck for interacting with the window manager"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

import logging
from contextlib import contextmanager

import cairo
from gi.repository import Gdk, GdkX11, Wnck

from .util import clamp_idx, EnumSafeDict, Rectangle, Region, XInitError

# Workaround for MyPy type comment getting wrapped by code formatter
_Rect = Rectangle

# Allow MyPy to work without depending on the `typing` package
# (And silence complaints from only using the imported types in comments)
MYPY = False
if MYPY:
    # pylint: disable=unused-import
    from typing import Any, List, Optional, Sequence, Tuple, Union  # NOQA
    from .util import Strut  # NOQA
del MYPY

#: Lookup table for internal window gravity support.
#: (libwnck's support is either unreliable or broken)
GRAVITY = EnumSafeDict({
    'NORTH_WEST': (0.0, 0.0),
    'NORTH': (0.5, 0.0),
    'NORTH_EAST': (1.0, 0.0),
    'WEST': (0.0, 0.5),
    'CENTER': (0.5, 0.5),
    'EAST': (1.0, 0.5),
    'SOUTH_WEST': (0.0, 1.0),
    'SOUTH': (0.5, 1.0),
    'SOUTH_EAST': (1.0, 1.0),
})
key, val = None, None  # Safety cushion for the "del" line.
for key, val in list(GRAVITY.items()):
    # Support GDK gravity constants
    GRAVITY[getattr(Gdk.Gravity, key)] = val

    # Support libwnck gravity constants
    _name = key.replace('_', '')
    GRAVITY[getattr(Wnck.WindowGravity, _name)] = val

# Prevent these temporary variables from showing up in the apidocs
del _name, key, val

# ---

@contextmanager
def persist_maximization(win, keep_maximize=True):
    """Context manager to persist maximization state after a reposition

    If C{keep_maximize=False}, this becomes a no-op to ease writing
    clean code which needs to support both behaviours.
    """
    # Unmaximize and record the types we may need to restore
    max_types, maxed = ['', '_horizontally', '_vertically'], []
    for maxtype in max_types:
        if getattr(win, 'is_maximized' + maxtype)():
            maxed.append(maxtype)
            getattr(win, 'unmaximize' + maxtype)()

    yield

    # Restore maximization if asked
    if maxed and keep_maximize:
        for maxtype in maxed:
            getattr(win, 'maximize' + maxtype)()


class WorkArea(object):
    """Helper to calculate and query available workarea on the desktop."""
    def __init__(self, gdk_screen, ignore_struts=False):
        # type: (Gdk.Screen, bool) -> None
        self.gdk_screen = gdk_screen
        self.gdk_display = gdk_screen.get_display()
        self.ignore_struts = ignore_struts

    def get_struts(self, root_win):  # type: (Gdk.Window) -> List[Strut]
        """Retrieve the struts from the root window if supported."""
        _net_wm_strut_partial = Gdk.Atom.intern("_NET_WM_STRUT_PARTIAL", True)
        if not self.gdk_screen.supports_net_wm_hint(_net_wm_strut_partial):
            return []

        # Gather all struts
        struts = [root_win.property_get(root_win, _net_wm_strut_partial)]
        if self.gdk_screen.supports_net_wm_hint("_NET_CLIENT_LIST"):
            # Source: http://stackoverflow.com/a/11332614/435253
            for wid in root_win.property_get('_NET_CLIENT_LIST')[2]:
                w = GdkX11.X11Window.foreign_new_for_display(self.gdk_display,
                                                             wid)
                struts.append(w.property_get("_NET_WM_STRUT_PARTIAL"))
        struts = [tuple(x[2]) for x in struts if x]

        logging.debug("Gathered _NET_WM_STRUT_PARTIAL values:\n\t%s",
                      struts)
        return struts

    def subtract_struts(self, usable_region,  # type: Region
                        struts                # type: Sequence[Strut]
                        ):  # type: (...) -> Tuple[Rectangle, Region]
        """Subtract the given struts from the given region."""

        # Subtract the struts from the usable region
        _Sub = lambda *g: usable_region.subtract(
            Region(Rectangle(*g)))
        _w, _h = self.gdk_screen.get_width(), self.gdk_screen.get_height()
        for g in struts:  # pylint: disable=invalid-name
            # http://standards.freedesktop.org/wm-spec/1.5/ar01s05.html
            # XXX: Must not cache unless watching for notify events.
            _Sub(0, g[4], g[0], g[5] - g[4] + 1)             # left
            _Sub(_w - g[1], g[6], g[1], g[7] - g[6] + 1)     # right
            _Sub(g[8], 0, g[9] - g[8] + 1, g[2])             # top
            _Sub(g[10], _h - g[3], g[11] - g[10] + 1, g[3])  # bottom

        # Generate a more restrictive version used as a fallback
        usable_rect = usable_region.copy()
        _Sub = lambda *g: usable_rect.subtract(
            Region(Rectangle(*g)))
        for geom in struts:
            # http://standards.freedesktop.org/wm-spec/1.5/ar01s05.html
            # XXX: Must not cache unless watching for notify events.
            _Sub(0, geom[4], geom[0], _h)             # left
            _Sub(_w - geom[1], geom[6], geom[1], _h)  # right
            _Sub(0, 0, _w, geom[2])                   # top
            _Sub(0, _h - geom[3], _w, geom[3])        # bottom
            # TODO: The required "+ 1" in certain spots confirms that we're
            #       going to need unit tests which actually check that the
            #       WM's code for constraining windows to the usable area
            #       doesn't cause off-by-one bugs.
            # TODO: Share this on http://stackoverflow.com/q/2598580/435253
        return usable_rect.get_clipbox(), usable_region

    def get(self, monitor, ignore_struts=None):
        # type: (_Rect, bool) -> Tuple[Optional[Region], Optional[_Rect]]
        """Retrieve the usable area of the specified monitor using
        the most expressive method the window manager supports.

        @param monitor: The number or dimensions of the desired monitor.
        @param ignore_struts: If C{True}, just return the size of the whole
            monitor, allowing windows to overlap panels.

        @type monitor: L{Rectangle}
        @type ignore_struts: C{bool}

        @returns: The usable region and its largest rectangular subset.
        @rtype: L{Region}, L{Rectangle}
        """

        # Get the region and return failure early if it's empty
        usable_rect, usable_region = (monitor, Region(Rectangle(
            monitor.x, monitor.y, monitor.width, monitor.height)))
        if usable_region.is_empty():
            logging.error("WorkArea.get_monitor_rect received "
                          "an empty monitor region!")
            return None, None

        # Return early if asked to ignore struts
        if ignore_struts or (ignore_struts is None and self.ignore_struts):
            logging.debug("Panels ignored. Reported monitor geometry is:\n%s",
                          usable_rect)
            return usable_region, usable_rect

        # Get the list of struts from the root window
        root_win = self.gdk_screen.get_root_window()
        struts = self.get_struts(root_win)

        # Fall back to _NET_WORKAREA if we couldn't get any struts
        _net_workarea = Gdk.Atom.intern("_NET_WORKAREA", True)
        if struts:
            usable_rect, usable_region = self.subtract_struts(usable_region,
                                                              struts)
        elif self.gdk_screen.supports_net_wm_hint(_net_workarea):
            desktop_geo = tuple(root_win.property_get(_net_workarea)[2][0:4])
            logging.debug("Falling back to _NET_WORKAREA: %s", desktop_geo)
            usable_region.intersect(
                Region(Rectangle(*desktop_geo)))
            usable_rect = usable_region.get_clipbox()

        # FIXME: Only call get_rectangles if --debug
        logging.debug("Usable region of monitor calculated as:\n"
                      "\tRegion: %r\n\tRectangle: %r",
                      usable_region.get_rectangles(), usable_rect)
        return usable_region, usable_rect


class WindowManager(object):
    """A simple API-wrapper class for manipulating window positioning."""

    def __init__(self, screen=None, ignore_workarea=False):
        # type: (Gdk.Screen, bool) -> None
        """
        Initializes C{WindowManager}.

        @param screen: The X11 screen to operate on. If C{None}, the default
            screen as retrieved by C{Gdk.Screen.get_default} will be used.
        @type screen: C{Gdk.Screen}

        @todo: Confirm that the root window only changes on X11 server
               restart. (Something which will crash QuickTile anyway since
               PyGTK makes X server disconnects uncatchable.)

               It could possibly change while toggling "allow desktop icons"
               in KDE 3.x. (Not sure what would be equivalent elsewhere)
        """
        self.gdk_screen = screen or Gdk.Screen.get_default()
        if self.gdk_screen is None:
            raise XInitError("GTK+ could not open a connection to the X server"
                             " (bad DISPLAY value?)")
        self.gdk_display = self.gdk_screen.get_display()

        self.screen = Wnck.Screen.get(self.gdk_screen.get_number())
        self.workarea = WorkArea(self.gdk_screen,
                                 ignore_struts=ignore_workarea)

    @staticmethod
    def calc_win_gravity(geom, gravity):
        # (Rectangle, Tuple[float, float]) -> Tuple[int, int]
        """Calculate the X and Y coordinates necessary to simulate non-topleft
        gravity on a window.

        @param geom: The window geometry to which to apply the corrections.
        @param gravity: A desired gravity chosen from L{GRAVITY}.
        @type geom: L{Rectangle}
        @type gravity: C{Wnck.WindowGravity.*} or C{Gdk.Gravity.*}

        @returns: The coordinates to be used to achieve the desired position.
        @rtype: C{(x, y)}

        This exists because, for whatever reason, whether it's wnck, Openbox,
        or both at fault, the WM's support for window gravities seems to have
        no effect beyond double-compensating for window border thickness unless
        using C{WindowGravity.STATIC}.

        My best guess is that the gravity modifiers are being applied to the
        window frame rather than the window itself, hence static gravity would
        position correctly and north-west gravity would double-compensate for
        the titlebar and border dimensions.

        ...however, that still doesn't explain why the non-topleft gravities
        have no effect. I'm guessing something's just broken.
        """
        grav_x, grav_y = GRAVITY[gravity]

        return (
            int(geom.x - (geom.width * grav_x)),
            int(geom.y - (geom.height * grav_y))
        )

    @staticmethod
    def get_geometry_rel(window, monitor_geom):
        # type: (Wnck.Window, Rectangle) -> Rectangle
        """Get window position relative to the monitor rather than the desktop.

        @param monitor_geom: The rectangle returned by
            C{gdk.Screen.get_monitor_geometry}
        @type window: C{Wnck.Window}
        @type monitor_geom: L{Rectangle}

        @rtype: L{Rectangle}
        """
        win_geom = Rectangle(*window.get_geometry())
        win_geom = win_geom._replace(x=win_geom.x - monitor_geom.x,
                                     y=win_geom.y - monitor_geom.y)

        return win_geom

    def get_monitor(self, win):
        # type: (Wnck.Window) -> Tuple[int, Rectangle]
        """Given a C{Wnck.Window}, retrieve the monitor ID and geometry.

        @type win: C{Wnck.Window}
        @returns: A tuple containing the monitor ID and geometry.
        @rtype: C{(int, Rectangle)}
        """
        # TODO: Look for a way to get the monitor ID without having
        #       to instantiate a Gdk.Window
        if not isinstance(win, Gdk.Window):
            win = GdkX11.X11Window.foreign_new_for_display(self.gdk_display,
                                                           win.get_xid())

        # TODO: How do I retrieve the root window from a given one?
        monitor_id = self.gdk_screen.get_monitor_at_window(win)
        monitor_geom = self.gdk_screen.get_monitor_geometry(monitor_id)

        logging.debug(" Window is on monitor %s, which has geometry %s",
                      monitor_id, monitor_geom)
        return monitor_id, monitor_geom

    def _get_win_for_prop(self, window=None):
        # type: (Optional[Wnck.Window]) -> Gdk.Window
        """Retrieve a GdkWindow for a given WnckWindow, or the root if None."""
        if window:
            return Gdk.window_foreign_new(window.get_xid())
        else:
            return self.gdk_screen.get_root_window()

    def get_property(self, key, window=None):
        # type: (str, Optional[Wnck.Window]) -> Any
        """Retrieve the value of a property on the given window.

        @param window: If unset, the root window will be queried.
        @type window: C{Wnck.Window} or C{None}
        """
        return self._get_win_for_prop(window).property_get(key)

    def set_property(self, key,   # type: str
                     value,       # type: Union[Sequence[int], int, str]
                     window=None  # type: Optional[Wnck.Window]
                     ):           # type: (...) -> None
        """Set the value of a property on the given window.

        @param window: If unset, the root window will be queried.
        @type window: C{Wnck.Window} or C{None}
        """

        # TODO: Verify that this isn't supposed to be `bytes` instead
        if isinstance(value, str):
            prop_format = 8
            prop_type = "STRING"
        else:
            prop_format = 32
            prop_type = "CARDINAL"
            if isinstance(value, int):
                value = [value]

        self._get_win_for_prop(window).property_change(
            key, prop_type,
            prop_format, Gdk.PROP_MODE_REPLACE, value)

    def del_property(self, key, window=None):
        # type: (str, Optional[Wnck.Window]) -> None
        """Unset a property on the given window.

        @param window: If unset, the root window will be queried.
        @type window: C{Wnck.Window} or C{None}
        """
        self._get_win_for_prop(window).property_delete(key)

    def get_relevant_windows(self, workspace):
        """C{Wnck.Screen.get_windows} without WINDOW_DESKTOP/DOCK windows."""

        for window in self.screen.get_windows():
            # Skip windows on other virtual desktops for intuitiveness
            if workspace and not window.is_on_workspace(workspace):
                logging.debug("Skipping window on other workspace: %r", window)
                continue

            # Don't cycle elements of the desktop
            if not self.is_relevant(window):
                continue

            yield window

    def get_workspace(self,
                      window=None,      # type: Wnck.Window
                      direction=None,   # type: Wnck.MotionDirection
                      wrap_around=True  # type: bool
                      ):                # type: (...) -> Wnck.Workspace
        """Get a workspace relative to either a window or the active one.

        @param window: The point of reference. C{None} for the active workspace
        @param direction: The direction in which to look, relative to the point
            of reference. Accepts the following types:
             - C{Wnck.MotionDirection}: Non-cycling direction
             - C{int}: Relative index in the list of workspaces
             - C{None}: Just get the workspace object for the point of
               reference
        @param wrap_around: Whether relative indexes should wrap around.

        @type window: C{Wnck.Window} or C{None}
        @type wrap_around: C{bool}
        @rtype: C{Wnck.Workspace} or C{None}
        @returns: The workspace object or C{None} if no match could be found.
        """
        if window:
            cur = window.get_workspace()
        else:
            cur = self.screen.get_active_workspace()

        if not cur:
            return None  # It's either pinned or on no workspaces

        if isinstance(direction, Wnck.MotionDirection):
            nxt = cur.get_neighbor(direction)
        elif isinstance(direction, int):
            # TODO: Deduplicate with the wrapping code in commands.py
            n_spaces = self.screen.get_workspace_count()

            nxt = self.screen.get_workspace(
                clamp_idx(cur.get_number() + direction, n_spaces, wrap_around))

        elif direction is None:
            nxt = cur
        else:
            nxt = None
            logging.warn("Unrecognized direction: %r", direction)

        return nxt

    @staticmethod
    def is_relevant(window):
        # type: (Wnck.Window) -> bool
        """Return False if the window should be ignored.

        (eg. If it's the desktop or a panel)
        """
        if not window:
            logging.debug("Received no window object to manipulate")
            return False

        if window.get_window_type() in [
                Wnck.WindowType.DESKTOP,
                Wnck.WindowType.DOCK]:
            logging.debug("Irrelevant window: %r", window)
            return False

        # TODO: Support customizations to exclude things like my Conky window
        # (Which I can't make a `desktop` window because I sometimes drag it)

        return True

    def reposition(self,
            win,                                    # type: Wnck.Window
            geom=None,                              # type: Optional[Rectangle]
            monitor=Rectangle(0, 0, 0, 0),          # type: Rectangle
            keep_maximize=False,                    # type: bool
            gravity=Wnck.WindowGravity.NORTHWEST,
            geometry_mask=(
                Wnck.WindowMoveResizeMask.X |
                Wnck.WindowMoveResizeMask.Y |
                Wnck.WindowMoveResizeMask.WIDTH |
                Wnck.WindowMoveResizeMask.HEIGHT)
                   ):  # pylint: disable=too-many-arguments
        # type: (...) -> None
        # TODO: Complete MyPy type signature
        # pylint:disable=line-too-long
        """
        Position and size a window, decorations inclusive, according to the
        provided target window and monitor geometry rectangles.

        If no monitor rectangle is specified, position relative to the desktop
        as a whole.

        @param win: The C{Wnck.Window} to operate on.
        @param geom: The new geometry for the window. Can be left unspecified
            if the intent is to move the window to another monitor without
            repositioning it.
        @param monitor: The frame relative to which C{geom} should be
            interpreted. The whole desktop if unspecified.
        @param keep_maximize: Whether to re-maximize a maximized window after
            un-maximizing it to move it.
        @param gravity: A constant specifying which point on the window is
            referred to by the X and Y coordinates in C{geom}.
        @param geometry_mask: A set of flags determining which aspects of the
            requested geometry should actually be applied to the window.
            (Allows the same geometry definition to easily be shared between
            operations like move and resize.)
        @type win: C{Wnck.Window}
        @type geom: L{Rectangle} or C{None}
        @type monitor: L{Rectangle}
        @type keep_maximize: C{bool}
        @type gravity: U{WnckWindowGravity<https://developer.gnome.org/libwnck/stable/WnckWindow.html#WnckWindowGravity>} or U{GDK Gravity Constant<http://www.pygtk.org/docs/pyGdk-constants.html#gdk-gravity-constants>}
        @type geometry_mask: U{WnckWindowMoveResizeMask<https://developer.gnome.org/libwnck/2.30/WnckWindow.html#WnckWindowMoveResizeMask>}

        @todo 1.0.0: Look for a way to accomplish this with a cleaner method
            signature. This is getting a little hairy. (API-breaking change)
        """  # NOQA

        # We need to ensure that ignored values are still present for
        # gravity calculations.
        old_geom = self.get_geometry_rel(win, self.get_monitor(win)[1])
        if geom:
            for attr in ('x', 'y', 'width', 'height'):
                if not geometry_mask & getattr(Wnck,
                        'WINDOW_CHANGE_%s' % attr.upper()):
                    setattr(geom, attr, getattr(old_geom, attr))
        else:
            geom = old_geom

        with persist_maximization(win, keep_maximize):
            # Apply gravity and resolve to absolute desktop coordinates.
            new_x, new_y = self.calc_win_gravity(geom, gravity)
            new_x += monitor.x
            new_y += monitor.y

            logging.debug(" Repositioning to (%d, %d, %d, %d)\n",
                    new_x, new_y, geom.width, geom.height)

            # See the calc_win_gravity docstring for the rationale here
            win.set_geometry(Wnck.WindowGravity.STATIC, geometry_mask,
                    new_x, new_y, geom.width, geom.height)
