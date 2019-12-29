"""Wrapper around libwnck for interacting with the window manager"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

import logging
from contextlib import contextmanager

from Xlib.display import Display as XDisplay
from Xlib.error import DisplayConnectionError
from Xlib import Xatom

from gi.repository import Gdk, GdkX11, Wnck

from .util import (clamp_idx, Gravity, Rectangle, UsableRegion,
                   StrutPartial, XInitError)

# Allow MyPy to work without depending on the `typing` package
# (And silence complaints from only using the imported types in comments)
MYPY = False
if MYPY:
    # pylint: disable=unused-import
    from typing import (Any, Iterable, List, Optional, Sequence, Tuple,  # NOQA
                        Union)
del MYPY

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


class WindowManager(object):
    """A simple API-wrapper class for manipulating window positioning."""

    def __init__(self, screen=None, x_display=None):
        # type: (Gdk.Screen, XDisplay) -> None
        """
        Initializes C{WindowManager}.

        @param screen: The Gdk.Screen to operate on. If C{None}, the default
            screen as retrieved by C{Gdk.Screen.get_default} will be used.
        @type screen: C{Gdk.Screen}

        @param x_display: The X11 display to operate on. If C{None}, a new
            X connection will be created.
        @type x_display: C{Xlib.display.Display}

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

        try:
            self.x_display = x_display or XDisplay()
        except (UnicodeDecodeError, DisplayConnectionError) as err:
            raise XInitError("python-xlib failed with %s when asked to open"
                             " a connection to the X server. Cannot bind keys."
                             "\n\tIt's unclear why this happens, but it is"
                             " usually fixed by deleting your ~/.Xauthority"
                             " file and rebooting."
                             % err.__class__.__name__)
        self.x_screen = self.x_display.screen()
        self.x_root = self.x_screen.root

        self.screen = Wnck.Screen.get(self.gdk_screen.get_number())

        self.n_screens = None
        self.usable_region = self._load_desktop_geometry()
        # TODO: Hook monitor-added and monitor-removed and regenerate this
        # TODO: Hook changes to strut reservations and regenerate this

    def _load_desktop_geometry(self):
        """Retrieve and process monitor and panel shapes into a UsableRegion"""
        # Gather the screen rectangles
        self.n_screens = self.x_root.xinerama_get_screen_count().screen_count
        monitors = []
        for idx in range(0, self.n_screens):
            monitors.append(Rectangle.from_gdk(
                self.gdk_screen.get_monitor_geometry(idx)))
            # TODO: Look into using python-xlib to match x_root use

        usable_region = UsableRegion()
        usable_region.set_monitors(monitors)

        if not usable_region:
            logging.error("WorkArea._load_desktop_geometry received "
                          "an empty monitor region!")
            # TODO: What should I do at this point?

        # Gather all struts
        struts = []
        for wid in [self.x_root.id] + list(self.get_property(
                self.x_root.id, '_NET_CLIENT_LIST', Xatom.WINDOW, [])):
            win = self.x_display.create_resource_object('window', wid)
            result = self.get_property(
                win, '_NET_WM_STRUT_PARTIAL', Xatom.CARDINAL)
            if result:
                struts.append(StrutPartial(*result))
                logging.debug("Gathered _NET_WM_STRUT_PARTIAL value: %s",
                              struts)
            else:
                # TODO: Unit test this fallback
                result = self.get_property(
                    win, '_NET_WM_STRUT', Xatom.CARDINAL)
                if result:
                    struts.append(StrutPartial(*result))
                    logging.debug("Gathered _NET_WM_STRUT value: %s", struts)

        # Get the list of struts from the root window
        usable_region.set_panels(struts)
        logging.debug("Usable desktop region calculated as: %s", usable_region)
        return usable_region

    def get_monitor(self, win):
        # type: (Wnck.Window) -> Tuple[int, Rectangle]
        """Given a C{Wnck.Window}, retrieve the monitor ID and geometry.

        @type win: C{Wnck.Window}
        @returns: A tuple containing the monitor ID and geometry.
        @rtype: C{(int, Rectangle)}
        """
        # TODO: Look for a way to get the monitor ID without having
        #       to instantiate a Gdk.Window. Doing so would also remove
        #       the need to set self.gdk_display as this is the only user of it
        if not isinstance(win, Gdk.Window):
            win = GdkX11.X11Window.foreign_new_for_display(self.gdk_display,
                                                           win.get_xid())

        # TODO: How do I retrieve the root window from a given one?
        # (Gdk.Display.get_default_screen().get_root_window()... now why?)
        monitor_id = self.gdk_screen.get_monitor_at_window(win)
        monitor_geom = self.gdk_screen.get_monitor_geometry(monitor_id)

        logging.debug(" Window is on monitor %s, which has geometry %s",
                      monitor_id, monitor_geom)
        return monitor_id, monitor_geom

    def get_relevant_windows(self, workspace):
        # type: (Wnck.Workspace) -> Iterable[Wnck.Window]
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

    def _property_prep(self, win, name):
        """Common code for get_property and set_property"""
        if isinstance(win, (Gdk.Window, Wnck.Window)):
            win = win.get_xid()

        if isinstance(win, int):
            win = self.x_display.create_resource_object('window', win)
        if isinstance(name, str):
            name = self.x_display.get_atom(name)
        return win, name

    def get_property(self, win, name, prop_type, empty=None):
        """Helper to make querying X11 properties cleaner"""
        win, name = self._property_prep(win, name)

        result = win.get_full_property(name, prop_type)
        return result.value if result else empty
        # TODO: Verify that python-xlib will call XFree for us when appropriate

    def set_property(self, win, name, value,  # pylint: disable=R0913
            prop_type=Xatom.STRING, format_size=8):
        """Helper to make setting X11 properties cleaner"""
        win, name = self._property_prep(win, name)
        win.change_property(name, prop_type, format_size, value)
        # TODO: Set an `onerror` handler and at least log an error to console

    # XXX: Move `if not window` into a decorator and use it everywhere?
    @staticmethod
    def is_relevant(window):  # type: (Wnck.Window) -> bool
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
            gravity=Gravity.TOP_LEFT,               # type: Gravity
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
        @type gravity: C{Gravity}
        @type geometry_mask: U{WnckWindowMoveResizeMask<https://developer.gnome.org/libwnck/2.30/WnckWindow.html#WnckWindowMoveResizeMask>}

        @todo 1.0.0: Look for a way to accomplish this with a cleaner method
            signature. This is getting a little hairy. (API-breaking change)
        """  # NOQA

        # We need to ensure that ignored values are still present for
        # gravity calculations.
        old_geom = Rectangle(*win.get_geometry()).to_relative(
            self.get_monitor(win)[1])

        new_args = {}
        if geom:
            for attr in ('x', 'y', 'width', 'height'):
                if geometry_mask & getattr(Wnck.WindowMoveResizeMask,
                        attr.upper()):
                    new_args[attr] = getattr(geom, attr)

        new_geom = old_geom._replace(**new_args)

        # Apply gravity and resolve to absolute desktop coordinates.
        new_geom = new_geom.from_gravity(gravity).from_relative(monitor)

        # Ensure the window is fully within the monitor
        # TODO: Make this remember the original position and re-derive from it
        #       on each monitor-next call as long as the window hasn't changed
        #       (Ideally, re-derive from the tiling preset if set)
        if monitor and not geom:
            new_geom = new_geom.moved_into(monitor)

        logging.debug(" Repositioning to %s)\n", new_geom)
        with persist_maximization(win, keep_maximize):
            # Always use STATIC because either WMs implement window gravity
            # incorrectly or it's not applicable to this problem
            win.set_geometry(Wnck.WindowGravity.STATIC,
                             geometry_mask, *new_geom)
