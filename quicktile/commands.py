"""Available window-management commands"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

import json, logging, time
from functools import wraps

from Xlib import Xatom

import gi
gi.require_version('Gdk', '3.0')
gi.require_version('Wnck', '3.0')

from gi.repository import Gdk, GdkX11, Wnck
from gi.repository.Wnck import MotionDirection

from .layout import resolve_fractional_geom, GravityLayout
from .util import Rectangle, clamp_idx, fmt_table

# Allow MyPy to work without depending on the `typing` package
# (And silence complaints from only using the imported types in comments)
MYPY = False
if MYPY:
    # pylint: disable=unused-import
    from typing import (Any, Callable, Dict, Iterable, Iterator, List,  # NOQA
                        Optional, Sequence, Tuple)
    from typing import Mapping as Map  # NOQA
    from mypy_extensions import VarArg, KwArg  # NOQA

    from .wm import WindowManager  # NOQA
    from .util import CommandCB, Gravity    # NOQA

    # FIXME: Replace */** with a dict so I can be strict here
    CommandCBWrapper = Callable[..., Any]  # pylint: disable=invalid-name
del MYPY


class CommandRegistry(object):
    """Handles lookup and boilerplate for window management commands.

    Separated from WindowManager so its lifecycle is not tied to a specific
    GDK Screen object.
    """

    extra_state = {}  # type: Dict[str, Any]

    def __init__(self):     # type: () -> None
        self.commands = {}  # type: Dict[str, CommandCBWrapper]
        self.help = {}      # type: Dict[str, str]

    def __iter__(self):  # type: () -> Iterator[str]
        for name in self.commands:
            yield name

    def __str__(self):   # type: () -> str
        return fmt_table(self.help, ('Known Commands', 'desc'), group_by=1)

    @staticmethod
    def get_window_meta(window,  # type: Wnck.Window
                        state,  # type: Dict[str, Any]
                        winman  # type: WindowManager
                        ):  # type: (...) -> bool
        # Bail out early on None or things like the desktop window
        if not winman.is_relevant(window):
            return False

        win_rect = Rectangle(*window.get_geometry())
        # FIXME: Make calls to win.get_* lazy in case --debug
        #        wasn't passed.
        logging.debug("Operating on window %r with title \"%s\" "
                      "and geometry %r", window, window.get_name(), win_rect)

        monitor_id, monitor_geom = winman.get_monitor(window)
        use_rect = winman.usable_region.find_usable_rect(win_rect)

        # TODO: Replace this MPlayer safety hack with a properly
        #       comprehensive exception catcher.
        if not use_rect:
            logging.debug("Received a worthless value for largest "
                          "rectangular subset of desktop (%r). Doing "
                          "nothing.", use_rect)
            return False

        state.update({
            "monitor_id": monitor_id,
            "monitor_geom": monitor_geom,
            "usable_rect": use_rect,
        })
        return True

    def add(self, name, *p_args, **p_kwargs):
        # type: (str, *Any, **Any) -> Callable[[CommandCB], CommandCB]
        # TODO: Rethink the return value of the command function.
        """Decorator to wrap a function in boilerplate and add it to the
            command registry under the given name.

            NOTE: The `windowless` parameter allows a command to be registered
            as not requiring and active window.

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
            def wrapper(winman,       # type: WindowManager
                        window=None,  # type: Wnck.Window
                        *args,
                        **kwargs
                        ):            # type: (...) -> None

                window = window or winman.screen.get_active_window()

                state = {}
                state.update(self.extra_state)
                state["cmd_name"] = name

                # FIXME: Refactor to avoid this hack
                windowless = p_kwargs.get('windowless', False)
                if 'windowless' in p_kwargs:
                    del p_kwargs['windowless']

                # Bail out early on None or things like the desktop window
                if not (windowless or self.get_window_meta(
                        window, state, winman)):
                    logging.debug("No window and windowless=False")
                    return None

                args, kwargs = p_args + args, dict(p_kwargs, **kwargs)

                # TODO: Factor out this hack
                if 'cmd_idx' in kwargs:
                    state['cmd_idx'] = kwargs['cmd_idx']
                    del kwargs['cmd_idx']

                func(winman, window, state, *args, **kwargs)

            if name in self.commands:
                logging.warning("Redefining existing command: %s", name)
            self.commands[name] = wrapper

            if not func.__doc__:
                raise AssertionError("All commands must have a docstring: "
                                     "%r" % func)
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
            for pos, (cmd, arglist) in enumerate(command_map.items()):
                self.add(cmd, cmd_idx=pos, *arglist)(func)
            return func
        return decorate

    def call(self, command, winman, *args, **kwargs):
        # type: (str, WindowManager, *Any, **Any) -> bool
        """Resolve a textual positioning command and execute it."""
        cmd = self.commands.get(command, None)

        if cmd:
            logging.debug("Executing command '%s' with arguments %r, %r",
                          command, args, kwargs)
            cmd(winman, *args, **kwargs)

            # TODO: Allow commands to report success or failure
            return True
        else:
            logging.error("Unrecognized command: %s", command)
            return False


#: The instance of L{CommandRegistry} to be used in 99.9% of use cases.
commands = CommandRegistry()


def cycle_dimensions(winman,      # type: WindowManager
                     win,         # type: Any  # TODO: Consistent Window type
                     state,       # type: Dict[str, Any]
                     *dimensions  # type: Any
                     ):  # type: (...) -> Optional[Gdk.Rectangle]
    # TODO: Standardize on what kind of window object to pass around
    """Cycle the active window through a list of positions and shapes.

    Takes one step each time this function is called.

    If the window's dimensions are not within 100px (by euclidean distance)
    of an entry in the list, set them to the first list entry.

    @param dimensions: A list of tuples representing window geometries as
        floating-point values between 0 and 1, inclusive.
    @type dimensions: C{[(x, y, w, h), ...]}
    @type win: C{Gdk.Window}

    @returns: The new window dimensions.
    @rtype: C{Gdk.Rectangle}
    """
    win_geom = Rectangle(*win.get_geometry()).to_relative(
        state['monitor_geom'])

    # Get the bounding box for the usable region of the current monitor
    clip_box = state['usable_rect']

    logging.debug("Selected preset sequence:\n\t%r", dimensions)

    # Resolve proportional (eg. 0.5) and preserved (None) coordinates
    dims = [resolve_fractional_geom(i or win_geom, clip_box)
        for i in dimensions]
    if not dims:
        return None

    logging.debug("Selected preset sequence resolves to these monitor-relative"
                  " pixel dimensions:\n\t%r", dims)

    # TODO: Rewrite this position-getting code
    try:
        cmd_idx, pos = json.loads(winman.get_property(
            win, '_QUICKTILE_CYCLE_POS', Xatom.STRING))
    except (ValueError, TypeError):  # TODO: Is TypeError still possible?
        # TODO: Restructure so get_property and json.loads can be checked
        # separately and an error can be logged for anything other than
        # "property is not set".
        cmd_idx, pos = None, -1

    if cmd_idx == state.get('cmd_idx', 0):
        pos = (pos + 1) % len(dims)
    else:
        pos = 0

    # TODO: Rewrite this position-setting code
    winman.set_property(win, '_QUICKTILE_CYCLE_POS',
                        json.dumps((state.get('cmd_idx', 0), pos)))
    result = Rectangle(*dims[pos]).from_relative(clip_box)

    logging.debug("Target preset is %s relative to monitor %s",
                  result, clip_box)

    # If we're overlapping a panel, fall back to a monitor-specific
    # analogue to _NET_WORKAREA to prevent overlapping any panels and
    # risking the WM potentially meddling with the result of resposition()
    # TODO: Rewrite this to not use Regions
    test_result = result.intersect(clip_box)
    if not test_result == result:
        result = test_result
        logging.debug("Result exceeds usable (non-rectangular) region of "
                      "desktop. (overlapped a non-fullwidth panel?) Reducing "
                      "to within largest usable rectangle: %s", clip_box)

    logging.debug("Calling reposition() with default gravity and dimensions "
                  "%r", tuple(result))
    winman.reposition(win, result)
    return result


@commands.add('monitor-switch', force_wrap=True)
@commands.add('monitor-next', 1)
@commands.add('monitor-prev', -1)
def cycle_monitors(winman,            # type: WindowManager
                   win,               # type: Wnck.Window
                   state,             # type: Dict[str, Any]
                   step=1,            # type: int
                   force_wrap=False,  # type: bool
                   n_monitors=None    # type: Optional[int]
                   ):                 # type: (...) -> None
    """Cycle the active window between monitors while preserving position.

    @todo 1.0.0: Remove C{monitor-switch} in favor of C{monitor-next}
        (API-breaking change)
    """
    old_mon_id, _ = winman.get_monitor(win)
    n_monitors = n_monitors or winman.gdk_screen.get_n_monitors()
    do_wrapping = (state['config'].getboolean('general', 'MovementsWrap') or
                   force_wrap)

    new_mon_id = clamp_idx(old_mon_id + step, n_monitors, do_wrapping)
    new_mon_geom = winman.gdk_screen.get_monitor_geometry(new_mon_id)
    logging.debug("Moving window to monitor %s, which has geometry %s",
                  new_mon_id, new_mon_geom)

    winman.reposition(win, None, new_mon_geom, keep_maximize=True)


@commands.add('monitor-switch-all', force_wrap=True)
@commands.add('monitor-prev-all', -1)
@commands.add('monitor-next-all', 1)
def cycle_monitors_all(winman, win, state, step=1, force_wrap=False):
    # type: (WindowManager, Wnck.Window, Dict[str, Any], int, bool) -> None
    """Cycle all windows between monitors while preserving position."""
    n_monitors = winman.gdk_screen.get_n_monitors()
    curr_workspace = win.get_workspace()

    if not curr_workspace:
        logging.debug("get_workspace() returned None")
        return

    for window in winman.get_relevant_windows(curr_workspace):
        cycle_monitors(winman, window, state, step, force_wrap, n_monitors)


@commands.add_many({'move-to-{}'.format(name): [variant]
    for name, variant in GravityLayout.GRAVITIES.items()})
def move_to_position(winman,       # type: WindowManager
                     win,          # type: Wnck.Window
                     state,        # type: Dict[str, Any]
                     gravity,      # type: Gravity
                     ):  # type: (...) -> None
    """Move window to a position on the screen, preserving its dimensions."""
    usable_rect = state['usable_rect']

    # TODO: Think about ways to refactor scaling for better maintainability
    win_rect = Rectangle(*win.get_geometry())
    target = Rectangle(
        x=gravity.value[0] * usable_rect.width,
        y=gravity.value[1] * usable_rect.height,
        width=win_rect.width,
        height=win_rect.height)
    logging.debug("Calling reposition() with %r gravity and dimensions %r",
                  gravity, tuple(target))

    winman.reposition(win, target, usable_rect,
        gravity=gravity,
        geometry_mask=Wnck.WindowMoveResizeMask.X |
                      Wnck.WindowMoveResizeMask.Y)


@commands.add('bordered')
def toggle_decorated(winman, win, state):  # pylint: disable=unused-argument
    # type: (WindowManager, Wnck.Window, Any) -> None
    """Toggle window decoration state on the active window."""

    # TODO: Switch to setting this via python-xlib
    display = winman.gdk_screen.get_display()
    win = GdkX11.X11Window.foreign_new_for_display(display, win.get_xid())
    win.set_decorations(Gdk.WMDecoration(0) if win.get_decorations()[1]
        else Gdk.WMDecoration.ALL)


@commands.add('show-desktop', windowless=True)
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
    # type: (WindowManager, Wnck.Window, Map[str, Any], str, str, bool) -> None
    """Toggle window state on the active window.

    @param command: The C{Wnck.Window} method name to be conditionally prefixed
        with "un", resolved, and called.
    @param check: The C{Wnck.Window} method name to be called to check
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
    # type: (WindowManager, Wnck.Window, Map[str, Any], str) -> None
    """Ask the Window Manager to begin a keyboard-driven operation."""

    getattr(win, 'keyboard_' + command)()


@commands.add('workspace-go-next', 1, windowless=True)
@commands.add('workspace-go-prev', -1, windowless=True)
@commands.add('workspace-go-up', MotionDirection.UP, windowless=True)
@commands.add('workspace-go-down', MotionDirection.DOWN, windowless=True)
@commands.add('workspace-go-left', MotionDirection.LEFT, windowless=True)
@commands.add('workspace-go-right', MotionDirection.RIGHT, windowless=True)
def workspace_go(winman, win, state, motion):  # pylint: disable=W0613
    # type: (WindowManager, Wnck.Window, Map[str,Any], MotionDirection) -> None
    """Switch the active workspace (next/prev wrap around)"""

    target = winman.get_workspace(None, motion,
        wrap_around=state['config'].getboolean('general', 'MovementsWrap'))

    if not target:
        logging.debug("Couldn't get the active workspace.")
        return

    logging.debug("Activating workspace %s", target)
    target.activate(int(time.time()))


@commands.add('workspace-send-next', 1)
@commands.add('workspace-send-prev', -1)
@commands.add('workspace-send-up', MotionDirection.UP)
@commands.add('workspace-send-down', MotionDirection.DOWN)
@commands.add('workspace-send-left', MotionDirection.LEFT)
@commands.add('workspace-send-right', MotionDirection.RIGHT)
# pylint: disable=unused-argument
def workspace_send_window(winman, win, state, motion):
    # type: (WindowManager, Wnck.Window, Map[str,Any], MotionDirection) -> None
    """Move the active window to another workspace (next/prev wrap around)"""

    target = winman.get_workspace(win, motion,
        wrap_around=state['config'].getboolean('general', 'MovementsWrap'))

    if not target:
        return  # It's either pinned, on no workspaces, or there is no match

    win.move_to_workspace(target)

# vim: set sw=4 sts=4 expandtab :
