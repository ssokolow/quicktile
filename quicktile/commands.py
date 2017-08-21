"""Available window-management commands"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

import logging, time
from functools import wraps
from heapq import heappop, heappush

import gtk.gdk, wnck  # pylint: disable=import-error

from .wm import GRAVITY
from .util import fmt_table

# Allow MyPy to work without depending on the `typing` package
# (And silence complaints from only using the imported types in comments)
try:
    # pylint: disable=unused-import
    from typing import (Any, Callable, Dict, Iterable, Iterator, List,  # NOQA
                        Optional, Sequence, Tuple, TYPE_CHECKING)
    from mypy_extensions import VarArg, KwArg  # NOQA

    if TYPE_CHECKING:
        from .wm import WindowManager  # NOQA
        from .util import CommandCB

    # FIXME: Replace */** with a dict so I can be strict here
    CommandCBWrapper = Callable[..., Any]
except:  # pylint: disable=bare-except
    pass

class CommandRegistry(object):
    """Handles lookup and boilerplate for window management commands.

    Separated from WindowManager so its lifecycle is not tied to a specific
    GDK Screen object.
    """

    def __init__(self):  # type: () -> None
        self.commands = {}  # type: Dict[str, CommandCBWrapper]
        self.help = {}      # type: Dict[str, str]

    def __iter__(self):  # type: () -> Iterator[str]
        for x in self.commands:
            yield x

    def __str__(self):   # type: () -> str
        return fmt_table(self.help, ('Known Commands', 'desc'), group_by=1)

    def add(self, name, *p_args, **p_kwargs):
        # type: (str, *Any, **Any) -> Callable[[CommandCB], CommandCB]
        # TODO: Rethink the return value of the command function.
        """Decorator to wrap a function in boilerplate and add it to the
            command registry under the given name.

            @param name: The name to know the command by.
            @param p_args: Positional arguments to prepend to all calls made
                via C{name}.
            @param p_kwargs: Keyword arguments to prepend to all calls made
                via C{name}.

            @type name: C{str}
            """

        def decorate(func):  # type: (CommandCB) -> CommandCB
            """Closure used to allow decorator to take arguments"""
            @wraps(func)
            # pylint: disable=missing-docstring
            def wrapper(winman, window=None, *args, **kwargs):
                # TODO: Add a MyPy type signature

                # Get Wnck and GDK window objects
                window = window or winman.screen.get_active_window()
                if isinstance(window, gtk.gdk.Window):
                    win = wnck.window_get(window.xid)  # pylint: disable=E1101
                else:
                    win = window

                # pylint: disable=no-member
                if not win:
                    logging.debug("Received no window object to manipulate.")
                    return None
                elif win.get_window_type() == wnck.WINDOW_DESKTOP:
                    logging.debug("Received desktop window object. Ignoring.")
                    return None
                else:
                    # FIXME: Make calls to win.get_* lazy in case --debug
                    #        wasn't passed.
                    logging.debug("Operating on window 0x%x with title \"%s\" "
                                  "and geometry %r",
                                  win.get_xid(), win.get_name(),
                                  win.get_geometry())

                monitor_id, monitor_geom = winman.get_monitor(window)

                use_area, use_rect = winman.workarea.get(monitor_geom)

                # TODO: Replace this MPlayer safety hack with a properly
                #       comprehensive exception catcher.
                if not use_rect:
                    logging.debug("Received a worthless value for largest "
                                  "rectangular subset of desktop (%r). Doing "
                                  "nothing.", use_rect)
                    return None

                state = {
                    "cmd_name": name,
                    "monitor_id": monitor_id,
                    "monitor_geom": monitor_geom,
                    "usable_region": use_area,
                    "usable_rect": use_rect,
                }

                args, kwargs = p_args + args, dict(p_kwargs, **kwargs)
                func(winman, win, state, *args, **kwargs)

            if name in self.commands:
                logging.warn("Redefining existing command: %s", name)
            self.commands[name] = wrapper

            assert func.__doc__, ("Command must have a docstring: %r" % func)
            help_str = func.__doc__.strip().split('\n')[0].split('. ')[0]
            self.help[name] = help_str.strip('.')

            # Return the unwrapped function so decorators can be stacked
            # to define multiple commands using the same code with different
            # arguments
            return func
        return decorate

    def add_many(self, command_map):
        # type: (Dict[str, List[Any]]) -> Callable[[CommandCB], CommandCB]
        # TODO: Make this type signature more strict
        """Convenience decorator to allow many commands to be defined from
           the same function with different arguments.

           @param command_map: A dict mapping command names to argument lists.
           @type command_map: C{dict}
           """
        # TODO: Refactor and redesign for better maintainability
        def decorate(func):
            """Closure used to allow decorator to take arguments"""
            for cmd, arglist in command_map.items():
                self.add(cmd, *arglist)(func)
            return func
        return decorate

    def call(self, command, winman, *args, **kwargs):
        # type: (str, WindowManager, *Any, **Any) -> Any
        # TODO: Decide what to do about return values
        """Resolve a textual positioning command and execute it."""
        cmd = self.commands.get(command, None)

        if cmd:
            logging.debug("Executing command '%s' with arguments %r, %r",
                          command, args, kwargs)
            cmd(winman, *args, **kwargs)
        else:
            logging.error("Unrecognized command: %s", command)


#: The instance of L{CommandRegistry} to be used in 99.9% of use cases.
commands = CommandRegistry()

def cycle_dimensions(winman,      # type: WindowManager
                     win,         # type: Any  # TODO: Consistent Window type
                     state,       # type: Dict[str, Any]
                     *dimensions  # type: Any
                     ):  # type: (...) -> Optional[gtk.gdk.Rectangle]
    # type: (WindowManager, Any, Dict[str, Any], *Tuple[...]) ->
    # TODO: Standardize on what kind of window object to pass around
    """Cycle the active window through a list of positions and shapes.

    Takes one step each time this function is called.

    If the window's dimensions are not within 100px (by euclidean distance)
    of an entry in the list, set them to the first list entry.

    @param dimensions: A list of tuples representing window geometries as
        floating-point values between 0 and 1, inclusive.
    @type dimensions: C{[(x, y, w, h), ...]}
    @type win: C{gtk.gdk.Window}

    @returns: The new window dimensions.
    @rtype: C{gtk.gdk.Rectangle}
    """
    win_geom = winman.get_geometry_rel(win, state['monitor_geom'])
    usable_region = state['usable_region']

    # Get the bounding box for the usable region (overlaps panels which
    # don't fill 100% of their edge of the screen)
    clip_box = usable_region.get_clipbox()

    logging.debug("Selected preset sequence:\n\t%r", dimensions)

    # Resolve proportional (eg. 0.5) and preserved (None) coordinates
    dims = []
    for tup in dimensions:
        current_dim = []
        for pos, val in enumerate(tup):
            if val is None:
                current_dim.append(tuple(win_geom)[pos])
            else:
                # FIXME: This is a bit of an ugly way to get (w, h, w, h)
                # from clip_box.
                current_dim.append(int(val * tuple(clip_box)[2 + pos % 2]))

        dims.append(current_dim)

    if not dims:
        return None

    logging.debug("Selected preset sequence resolves to these monitor-relative"
                  " pixel dimensions:\n\t%r", dims)

    # Calculate euclidean distances between the window's current geometry
    # and all presets and store them in a min heap.
    euclid_distance = []  # type: List[Tuple[int, int]]
    for pos, val in enumerate(dims):
        distance = sum([(wg - vv) ** 2 for (wg, vv)
                        in zip(tuple(win_geom), tuple(val))]) ** 0.5
        heappush(euclid_distance, (distance, pos))

    # If the window is already on one of the configured geometries, advance
    # to the next configuration. Otherwise, use the first configuration.
    min_distance = heappop(euclid_distance)
    if float(min_distance[0]) / tuple(clip_box)[2] < 0.1:
        pos = (min_distance[1] + 1) % len(dims)
    else:
        pos = 0
    result = gtk.gdk.Rectangle(*dims[pos])

    logging.debug("Target preset is %s relative to monitor %s",
                  result, clip_box)
    result.x += clip_box.x
    result.y += clip_box.y

    # If we're overlapping a panel, fall back to a monitor-specific
    # analogue to _NET_WORKAREA to prevent overlapping any panels and
    # risking the WM potentially meddling with the result of resposition()
    if not usable_region.rect_in(result) == gtk.gdk.OVERLAP_RECTANGLE_IN:
        result = result.intersect(state['usable_rect'])
        logging.debug("Result exceeds usable (non-rectangular) region of "
                      "desktop. (overlapped a non-fullwidth panel?) Reducing "
                      "to within largest usable rectangle: %s",
                      state['usable_rect'])

    logging.debug("Calling reposition() with default gravity and dimensions "
                  "%r", tuple(result))
    winman.reposition(win, result)
    return result

@commands.add('monitor-switch')
@commands.add('monitor-next', 1)
@commands.add('monitor-prev', -1)
def cycle_monitors(winman, win, state, step=1):
    # type: (WindowManager, Any, Any, int) -> None
    """Cycle the active window between monitors while preserving position.

    @todo 1.0.0: Remove C{monitor-switch} in favor of C{monitor-next}
        (API-breaking change)
    """
    mon_id = state['monitor_id']
    new_mon_id = (mon_id + step) % winman.gdk_screen.get_n_monitors()

    new_mon_geom = winman.gdk_screen.get_monitor_geometry(new_mon_id)
    logging.debug("Moving window to monitor %s, which has geometry %s",
                  new_mon_id, new_mon_geom)

    winman.reposition(win, None, new_mon_geom, keep_maximize=True)

@commands.add('monitor-prev-all', -1)
@commands.add('monitor-next-all', 1)
def cycle_monitors_all(winman, win, state, step=1):
    # type: (WindowManager, wnck.Window, Any, int) -> None
    """Cycle all windows between monitors while preserving position."""
    n_monitors = winman.gdk_screen.get_n_monitors()
    curr_workspace = win.get_workspace()

    if not curr_workspace:
        logging.debug("get_workspace() returned None")
        return

    for window in winman.screen.get_windows():
        # Skip windows on other virtual desktops for intuitiveness
        if not window.is_on_workspace(curr_workspace):
            logging.debug("Skipping window on other workspace")
            continue

        # Don't cycle elements of the desktop
        if window.get_window_type() in [
              wnck.WINDOW_DESKTOP, wnck.WINDOW_DOCK]:  # pylint: disable=E1101
            logging.debug("Skipping desktop/dock window")
            continue

        gdkwin = gtk.gdk.window_foreign_new(window.get_xid())
        mon_id = winman.gdk_screen.get_monitor_at_window(gdkwin)
        new_mon_id = (mon_id + step) % n_monitors

        new_mon_geom = winman.gdk_screen.get_monitor_geometry(new_mon_id)
        logging.debug(
            "Moving window %s to monitor 0x%d, which has geometry %s",
            hex(window.get_xid()), new_mon_id, new_mon_geom)

        winman.reposition(window, None, new_mon_geom, keep_maximize=True)

# pylint: disable=no-member
MOVE_TO_COMMANDS = {
    'move-to-top-left': [wnck.WINDOW_GRAVITY_NORTHWEST,
                         wnck.WINDOW_CHANGE_X | wnck.WINDOW_CHANGE_Y],
    'move-to-top': [wnck.WINDOW_GRAVITY_NORTH, wnck.WINDOW_CHANGE_Y],
    'move-to-top-right': [wnck.WINDOW_GRAVITY_NORTHEAST,
                          wnck.WINDOW_CHANGE_X | wnck.WINDOW_CHANGE_Y],
    'move-to-left': [wnck.WINDOW_GRAVITY_WEST, wnck.WINDOW_CHANGE_X],
    'move-to-center': [wnck.WINDOW_GRAVITY_CENTER,
                       wnck.WINDOW_CHANGE_X | wnck.WINDOW_CHANGE_Y],
    'move-to-right': [wnck.WINDOW_GRAVITY_EAST, wnck.WINDOW_CHANGE_X],
    'move-to-bottom-left': [wnck.WINDOW_GRAVITY_SOUTHWEST,
                            wnck.WINDOW_CHANGE_X | wnck.WINDOW_CHANGE_Y],
    'move-to-bottom': [wnck.WINDOW_GRAVITY_SOUTH, wnck.WINDOW_CHANGE_Y],
    'move-to-bottom-right': [wnck.WINDOW_GRAVITY_SOUTHEAST,
                             wnck.WINDOW_CHANGE_X | wnck.WINDOW_CHANGE_Y],
}

@commands.add_many(MOVE_TO_COMMANDS)
def move_to_position(winman,       # type: WindowManager
                     win,          # type: Any  # TODO: Make this specific
                     state,        # type: Dict[str, Any]
                     gravity,      # type: Any  # TODO: Make this specific
                     gravity_mask  # type: wnck.WindowMoveResizeMask
                     ):  # type: (...) -> None  # TODO: Decide on a return type
    """Move window to a position on the screen, preserving its dimensions."""
    use_rect = state['usable_rect']

    grav_x, grav_y = GRAVITY[gravity]
    dims = (int(use_rect.width * grav_x), int(use_rect.height * grav_y), 0, 0)
    result = gtk.gdk.Rectangle(*dims)
    logging.debug("Calling reposition() with %r gravity and dimensions %r",
                  gravity, tuple(result))

    # pylint: disable=no-member
    winman.reposition(win, result, use_rect, gravity=gravity,
            geometry_mask=gravity_mask)

@commands.add('bordered')
def toggle_decorated(winman, win, state):  # pylint: disable=unused-argument
    # type: (WindowManager, wnck.Window, Any) -> None
    """Toggle window state on the active window."""
    win = gtk.gdk.window_foreign_new(win.get_xid())
    win.set_decorations(not win.get_decorations())

@commands.add('show-desktop')
def toggle_desktop(winman, win, state):  # pylint: disable=unused-argument
    # type: (WindowManager, Any, Any) -> None
    """Toggle "all windows minimized" to view the desktop"""
    target = not winman.screen.get_showing_desktop()
    winman.screen.toggle_showing_desktop(target)

@commands.add('all-desktops', 'pin', 'is_pinned')
@commands.add('fullscreen', 'set_fullscreen', 'is_fullscreen', True)
@commands.add('vertical-maximize', 'maximize_vertically',
                                   'is_maximized_vertically')
@commands.add('horizontal-maximize', 'maximize_horizontally',
                                     'is_maximized_horizontally')
@commands.add('maximize', 'maximize', 'is_maximized')
@commands.add('minimize', 'minimize', 'is_minimized')
@commands.add('always-above', 'make_above', 'is_above')
@commands.add('always-below', 'make_below', 'is_below')
@commands.add('shade', 'shade', 'is_shaded')
# pylint: disable=unused-argument,too-many-arguments
def toggle_state(winman, win, state, command, check, takes_bool=False):
    # type: (WindowManager, wnck.Window, Any, str, str, bool) -> None
    """Toggle window state on the active window.

    @param command: The C{wnck.Window} method name to be conditionally prefixed
        with "un", resolved, and called.
    @param check: The C{wnck.Window} method name to be called to check
        whether C{command} should be prefixed with "un".
    @param takes_bool: If C{True}, pass C{True} or C{False} to C{check} rather
        thank conditionally prefixing it with C{un} before resolving.
    @type command: C{str}
    @type check: C{str}
    @type takes_bool: C{bool}

    @todo 1.0.0: Rename C{vertical-maximize} and C{horizontal-maximize} to
        C{maximize-vertical} and C{maximize-horizontal}. (API-breaking change)
    """
    target = not getattr(win, check)()

    logging.debug("Calling action '%s' with state '%s'", command, target)
    if takes_bool:
        getattr(win, command)(target)
    else:
        getattr(win, ('' if target else 'un') + command)()

@commands.add('trigger-move', 'move')
@commands.add('trigger-resize', 'size')
# pylint: disable=unused-argument
def trigger_keyboard_action(winman, win, state, command):
    # type: (WindowManager, wnck.Window, Any, str) -> None
    """Ask the Window Manager to begin a keyboard-driven operation."""
    getattr(win, 'keyboard_' + command)()

@commands.add('workspace-go-next', 1)
@commands.add('workspace-go-prev', -1)
@commands.add('workspace-go-up', wnck.MOTION_UP)        # pylint: disable=E1101
@commands.add('workspace-go-down', wnck.MOTION_DOWN)    # pylint: disable=E1101
@commands.add('workspace-go-left', wnck.MOTION_LEFT)    # pylint: disable=E1101
@commands.add('workspace-go-right', wnck.MOTION_RIGHT)  # pylint: disable=E1101
def workspace_go(winman, win, state, motion):  # pylint: disable=W0613
    # type: (WindowManager, wnck.Window, Any, wnck.MotionDirection) -> None
    """Switch the active workspace (next/prev wrap around)"""
    target = winman.get_workspace(None, motion)
    if not target:
        return  # It's either pinned, on no workspaces, or there is no match
    target.activate(int(time.time()))

@commands.add('workspace-send-next', 1)
@commands.add('workspace-send-prev', -1)
@commands.add('workspace-send-up', wnck.MOTION_UP)      # pylint: disable=E1101
@commands.add('workspace-send-down', wnck.MOTION_DOWN)  # pylint: disable=E1101
@commands.add('workspace-send-left', wnck.MOTION_LEFT)  # pylint: disable=E1101
# pylint: disable=E1101
@commands.add('workspace-send-right', wnck.MOTION_RIGHT)
# pylint: disable=unused-argument
def workspace_send_window(winman, win, state, motion):
    # type: (WindowManager, wnck.Window, Any, wnck.MotionDirection) -> None
    """Move the active window to another workspace (next/prev wrap around)"""
    target = winman.get_workspace(win, motion)
    if not target:
        return  # It's either pinned, on no workspaces, or there is no match

    win.move_to_workspace(target)

# vim: set sw=4 sts=4 expandtab :
