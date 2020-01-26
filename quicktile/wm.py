"""Wrapper around libwnck for interacting with the window manager"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

# Silence PyLint being flat-out wrong about MyPy type annotations and
# complaining about my grouped imports
# pylint: disable=unsubscriptable-object
# pylint: disable=wrong-import-order

import logging
from contextlib import contextmanager

from Xlib.display import Display as XDisplay
from Xlib.error import DisplayConnectionError
from Xlib import Xatom

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('Wnck', '3.0')

from gi.repository import Gdk, GdkX11, Wnck

from .util import (clamp_idx, Gravity, Rectangle, UsableRegion,
                   StrutPartial, XInitError)

# -- Type-Annotation Imports --
from typing import Any, Iterable, Optional, Tuple, Union
# ---


@contextmanager
def persist_maximization(win: Wnck.Window, keep_maximize: bool=True):
    """Context manager to persist maximization state after a call to
    :any:`WindowManager.reposition`.

    :param win: The window to operate on.
    :param keep_maximize: If :any:`False`, this decoration becomes a no-op to
        ease writing clean code which needs to support both behaviours.
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
    """A simple API-wrapper class for manipulating window positioning.

    :param screen: The screen to operate on. If :any:`None`, the
        default screen as retrieved by :any:`Gdk.Screen.get_default` will
        be used.
    :param x_display: The ``Xlib.display.Display`` to operate on. If
        :any:`None`, a new X connection will be created.
    :raises XInitError: :any:`None` was specified for ``x_display`` and the
        attempt to open a new X connection failed.

    .. todo:: Confirm the root window only changes on X11 server restart
       and check whether PyGI retains the PyGTK behaviour of making
       connection loss an uncatchable hard exit.

       (It could possibly change while toggling "allow desktop icons"
       in KDE 3.x. Not sure what would be equivalent elsewhere.)
    """

    def __init__(self, screen: Gdk.Screen=None, x_display: XDisplay=None):
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

        self.usable_region = UsableRegion()
        self._load_desktop_geometry()
        # TODO: Hook monitor-added and monitor-removed and regenerate this
        # TODO: Hook changes to strut reservations and regenerate this

    def _load_desktop_geometry(self):
        """Retrieve monitor & panel shapes from the desktop and process them
        into a :class:`quicktile.util.UsableRegion` for easy querying.

        :raises Exception: Unable to retrieve monitor geometries

        .. todo:: Use a more specific exception.
        .. todo:: Either rework :any:`_load_desktop_geometry` into a public
           "update cached geometry" function or disable display of
           private members.
        .. todo:: Investigate going back to calling
           :meth:`_load_desktop_geometry` before every command.

        """

        # Work around xinerama_get_screen_count not getting registered in
        # python-xlib if the XINERAMA extension isn't loaded in the host
        # X session by using Gdk's API instead, which just returns 1.
        #
        # NOTE: Not using Gdk.Display.get_n_monitors because Kubuntu 16.04 LTS
        # doesn't have a new enough Gdk to have that API.
        n_screens = self.gdk_screen.get_n_monitors()
        monitors = []
        for idx in range(0, n_screens):
            monitors.append(Rectangle.from_gdk(
                self.gdk_screen.get_monitor_geometry(idx)))
            # TODO: Look into using python-xlib to match x_root use

        logging.debug("Loaded monitor geometry: %r", monitors)

        # Try to fail gracefully if monitors weren't found
        if monitors:
            self.usable_region.set_monitors(monitors)
        else:
            if self.usable_region:
                logging.error("WorkArea._load_desktop_geometry received "
                              "an empty monitor region! Using cached value.")
                return
            else:
                raise Exception("Could not retrieve desktop geometry")

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
        self.usable_region.set_panels(struts)
        logging.debug("Usable desktop region calculated as: %s",
            self.usable_region)
        return

    def get_monitor(self, win: Wnck.Window) -> Tuple[int, Rectangle]:
        """Given a window, retrieve the ID and geometry of the monitor it's on.

        :param win: The window to find the containing monitor for.
        :returns: ``(monitor_id, geometry)``

        .. todo:: Look for a way to get the monitor ID without having to
           instantiate a :class:`Gdk.Window`.

           Doing so would also remove the need to set ``self.gdk_display`` as
           this is the only user of it.
        """
        if not isinstance(win, Gdk.Window):
            win = GdkX11.X11Window.foreign_new_for_display(self.gdk_display,
                                                           win.get_xid())

        # TODO: How do I retrieve the root window from a given one?
        # (Gdk.Display.get_default_screen().get_root_window()... now why did
        # I want to know?)
        monitor_id = self.gdk_screen.get_monitor_at_window(win)
        monitor_geom = self.gdk_screen.get_monitor_geometry(monitor_id)

        logging.debug(" Window is on monitor %s, which has geometry %s",
                      monitor_id, Rectangle.from_gdk(monitor_geom))
        return monitor_id, monitor_geom

    def get_relevant_windows(self, workspace: Wnck.Workspace
                             ) -> Iterable[Wnck.Window]:
        """Wrapper for :meth:`Wnck.Screen.get_windows` that filters out windows
        of type :any:`Wnck.WindowType.DESKTOP` or :any:`Wnck.WindowType.DOCK`.

        :param workspace: The virtual desktop to retrieve windows from.
        """
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
                window: Wnck.Window=None,
                direction: Union[Wnck.MotionDirection, int]=None,
                wrap_around: bool=True,
                      ) -> Optional[Wnck.Workspace]:
        """Get a workspace (virtual desktop) relative to the one containing
        the given or active window.

        :param window: The point of reference. :any:`None` for the
            active workspace.
        :param direction: The direction in which to look, relative to the point
            of reference. Accepts the following types:

            - :any:`Wnck.MotionDirection`: Absolute direction (will not cycle
              around when it reaches the edge)
            - :any:`int`: Relative position in the list of workspaces (eg.
              ``1`` or ``-2``).
            - :any:`None`: The workspace containing ``window``
        :param wrap_around: Whether relative indexes should wrap around.
        :returns: The workspace object or :any:`None` if no match was found.
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
            logging.warning("Unrecognized direction: %r", direction)

        return nxt

    def _property_prep(self,
            win: Union[Gdk.Window, Wnck.Window, int],
            name: Union[str, int]):
        """Common code for `get_property` and `set_property`

        :param win: A GTK or Wnck Window object or a raw X11 window ID.
        :param name: An atom name or a handle returned by
            :meth:`Xlib.display.Display.create_resource_object`.

        .. todo:: Hide :meth:`_property_prep` from the docs
        """
        if isinstance(win, (Gdk.Window, Wnck.Window)):
            win = win.get_xid()

        if isinstance(win, int):
            win = self.x_display.create_resource_object('window', win)
        if isinstance(name, str):
            name = self.x_display.get_atom(name)
        return win, name

    # pylint: disable=line-too-long
    def get_property(self,
            win: Union[Gdk.Window, Wnck.Window, int],
            name: Union[str, int],
            prop_type: int,
            empty: Any=None):
        """Get the value of the X11 property ``name`` on window ``win``

        :param win: A GTK or Wnck Window object or a raw X11 window ID.
        :param name: An atom name or a handle returned by
            :meth:`Xlib.display.Display.create_resource_object`.
        :param prop_type: A constant from :mod:`Xlib.Xatom`
        :param empty: The value to return if the property is unset.

        As this is a semi-internal API not meriting *too* much work to make
        pretty, the design follows the underlying `XGetWindowProperty`_ API.

        Some variable names have been changed to avoid colliding with
        Python built-ins while others are abstracted away to present a
        simpler API.

        ``prop_type`` instructs the client library how to correctly un-marshall
        the data it receives.

        .. _XGetWindowProperty: https://tronche.com/gui/x/xlib/window-information/XGetWindowProperty.html

        .. TODO:: Verify that my ``empty`` argument to :meth:`get_property`
            obviates the need to specify anything other than
            ``AnyPropertyType`` for ``prop_type`` and, if so, factor it out.

        """  # NOQA
        win, name = self._property_prep(win, name)

        result = win.get_full_property(name, prop_type)
        return result.value if result else empty
        # TODO: Verify that python-xlib will call XFree for us when appropriate

    def set_property(self,  # pylint: disable=too-many-arguments
            win: Union[Gdk.Window, Wnck.Window, int],
            name: Union[str, int],
            value,
            prop_type: int=Xatom.STRING,
            format_size: int=8):
        """Set the value of X11 property ``name`` on window ``win`` to the
        contents of ``value``.

        :param win: A GTK or Wnck Window object or a raw X11 window ID.
        :param name: An atom name or a handle returned by
            :meth:`Xlib.display.Display.create_resource_object`.
        :param value: The value to be stored
        :param prop_type: A constant from :mod:`Xlib.Xatom`
        :param format_size: The size of the value in bits.

        As this is a semi-internal API not meriting *too* much work to make
        pretty, the design follows the underlying `XChangeProperty`_ API, which
        expects a C-style "list of items as a packed sequence of bits with
        out-of-band metadata" data type.

        Some variable names have been changed to avoid colliding with
        Python built-ins while others are abstracted away to present a
        simpler API.

        ``prop_type`` is metadata for the X client library to correctly
        un-marshall the data later and the server doesn't use it for
        anything.

        ``format_size`` specifies the size of an item in the sequence
        (even if it's a sequence of length 1) and is also necessary for
        correct operation if the X server decides that it needs to
        byte-swap the values.

        This is why ``format_size`` is necessary for things where you'd
        think that ``prop_type`` would be enough to describe the data type.

        .. _XChangeProperty: https://tronche.com/gui/x/xlib/window-information/XChangeProperty.html
        """  # NOQA pylint: disable=line-too-long
        win, name = self._property_prep(win, name)
        win.change_property(name, prop_type, format_size, value)
        self.x_display.flush()
        # TODO: Set an `onerror` handler and at least log an error to console

    # XXX: Move `if not window` into a decorator and use it everywhere?
    @staticmethod
    def is_relevant(window):  # type: (Wnck.Window) -> bool
        """Return :any:`False` if the window should be ignored.

        (i.e. If it's the desktop or a panel)
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

    def reposition(self,  # pylint: disable=too-many-arguments
            win: Wnck.Window,
            geom: Optional[Rectangle]=None,
            monitor: Rectangle=Rectangle(0, 0, 0, 0),
            keep_maximize: bool=False,
            gravity: Gravity=Gravity.TOP_LEFT,
            geometry_mask: Wnck.WindowMoveResizeMask=(
                Wnck.WindowMoveResizeMask.X |
                Wnck.WindowMoveResizeMask.Y |
                Wnck.WindowMoveResizeMask.WIDTH |
                Wnck.WindowMoveResizeMask.HEIGHT)
                   ) -> None:
        """
        Move and resize a window, decorations inclusive, according to the
        provided target window and monitor geometry rectangles.

        If no monitor rectangle is specified, the target position will be
        relative to the desktop as a whole.

        :param win: The window to reposition.
        :param geom: The new geometry for the window. Can be left unspecified
            if the intent is to move the window to another monitor without
            repositioning it.
        :param monitor: The frame relative to which ``geom`` should be
            interpreted. The whole desktop if unspecified.
        :param keep_maximize: Whether to re-maximize the window if it had to be
            un-maximized to ensure it would move.
        :param gravity: A constant specifying which point on the window is
            referred to by the X and Y coordinates in ``geom``.
        :param geometry_mask: A set of flags determining which aspects of the
            requested geometry should actually be applied to the window.
            (Allows the same geometry definition to easily be shared between
            operations like move and resize.)

        .. todo:: Look for a way to accomplish this with a cleaner method
            signature. This is getting a little hairy.

        .. todo:: Decide how to refactor :meth:`reposition` to allow for
            smarter handling of position clamping when cycling windows through
            a sequence of differently sized monitors.
        """

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
        if bool(monitor) and not geom:
            new_geom = new_geom.moved_into(
                self.usable_region.find_usable_rect(monitor))  # type: ignore

        logging.debug(" Repositioning to %s)\n", new_geom)
        with persist_maximization(win, keep_maximize):
            # Always use STATIC because either WMs implement window gravity
            # incorrectly or it's not applicable to this problem
            win.set_geometry(Wnck.WindowGravity.STATIC,
                             geometry_mask, *new_geom)
