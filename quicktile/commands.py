"""Available window-management commands

.. todo:: Replace varargs with a dict so ``CommandCBWrapper`` can be strict.
"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

# Silence PyLint being flat-out wrong about MyPy type annotations and
# complaining about my grouped imports
# pylint: disable=unsubscriptable-object,invalid-sequence-index
# pylint: disable=wrong-import-order

import logging, math, time
from functools import wraps

from Xlib import Xatom

import gi
gi.require_version('Gdk', '3.0')
gi.require_version('GdkX11', '3.0')
gi.require_version('Wnck', '3.0')

from gi.repository import Gdk, GdkX11, Wnck
from gi.repository.Wnck import MotionDirection

from .layout import resolve_fractional_geom, GravityLayout
from .util import Rectangle, clamp_idx, fmt_table

# -- Type-Annotation Imports --
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple, Union

from .wm import WindowManager
from .util import CommandCB, Gravity

#: MyPy type alias for what gets stored in `CommandRegistry`
CommandCBWrapper = Callable[..., Any]  # pylint: disable=invalid-name
# --


class CommandRegistry:
    """Lookup and dispatch boilerplate for window management commands."""

    #: Fields to be added to the ``state`` argument when calling commands
    extra_state: Dict[str, Any] = {}

    def __init__(self) -> None:
        self.commands: Dict[str, CommandCBWrapper] = {}
        self.help: Dict[str, str] = {}

    def __iter__(self) -> Iterator[str]:
        for name in self.commands:
            yield name

    def __str__(self) -> str:
        """Pretty-print a table of registered commands"""
        return fmt_table(self.help, ('Known Commands', 'desc'), group_by=1)

    @staticmethod
    def get_window_meta(
            window: Wnck.Window, state: Dict[str, Any], winman: WindowManager
    ) -> bool:
        """Gather information about ``window`` to pass to the command

        :param window: The window to inspect.
        :param state: The metadata dict to :meth:`dict.update` with gathered
            values.
        :returns: A boolean indicating success or failure.

        .. todo:: Is the MPlayer safety hack in :meth:`get_window_meta` still
            necessary with the refactored window-handling code?
        .. todo:: Can the :func:`logging.debug` call in :meth:`get_window_meta`
            be reworked to call :meth:`Wnck.Window.get_name` lazily?
        """
        # Bail out early on None or things like the desktop window
        if not winman.is_relevant(window):
            return False

        win_rect = Rectangle(*window.get_geometry())
        logging.debug("Operating on window %r with title \"%s\" "
                      "and geometry %r", window, window.get_name(), win_rect)

        monitor_id, monitor_geom = winman.get_monitor(window)

        # MPlayer safety hack
        if not winman.usable_region:
            logging.debug("Received a worthless value for largest "
                          "rectangular subset of desktop (%r). Doing "
                          "nothing.", winman.usable_region)
            return False

        state.update({
            "monitor_id": monitor_id,
            "monitor_geom": monitor_geom,
        })
        return True

    def add(self, name: str, *p_args: Any, **p_kwargs: Any
            ) -> Callable[[CommandCB], CommandCB]:
        """Decorator to wrap a function in boilerplate and add it to the
            command registry under the given name.

            :note: The ``windowless`` parameter allows a command to be
                registered as not requiring an active window.

            :param name: The name to register the command for lookup by.
            :param p_args: Positional arguments to prepend to all calls made
                via ``name``.
            :param p_kwargs: Keyword arguments to prepend to all calls made
                via ``name``.
            :param bool windowless: Allow the command to be invoked when no
                relevant active window can be retrieved.

            :raises AssertionError: Raised if the wrapped function has no
                docstring.

            .. todo:: Refactor :meth:`add` to make it less of an ugly pile.
            .. todo:: Rethink the return value expected of command functions.
            """

        def decorate(func: CommandCB) -> CommandCB:
            """Closure used to allow decorator to take arguments"""
            # Extract windowless before wrapper so it's stable across calls
            windowless = p_kwargs.pop('windowless', False)

            @wraps(func)
            # pylint: disable=missing-docstring,keyword-arg-before-vararg
            def wrapper(winman: WindowManager,
                        window: Wnck.Window = None,
                        *args,
                        **kwargs
                        ) -> None:

                window = window or winman.screen.get_active_window()

                state = {}
                state.update(self.extra_state)
                state["cmd_name"] = name

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
                return None

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

    def add_many(self, command_map: Dict[str, List[Any]]
                 ) -> Callable[[CommandCB], CommandCB]:
        """Convenience decorator to call :meth:`add` repeatedly to assing
           multiple command names to the same function which differ only in
           their arguments.

           :param command_map: A dict mapping command names to lists of
                arguments.

           .. todo:: Refactor and redesign :meth:`add_many` for better
              maintainability.
           """
        # TODO: What's the type signature on `decorate`?
        def decorate(func):
            """Closure used to allow decorator to take arguments"""
            for pos, (cmd, arglist) in enumerate(command_map.items()):
                self.add(cmd, cmd_idx=pos, *arglist)(func)
            return func
        return decorate

    def call(self,
            command: str,
            winman: WindowManager,
            *args: Any,
            **kwargs: Any) -> bool:
        """Look up a registered command by name and execute it.

        :param command: The name of the command to execute.
        :param args: Positional arguments to pass to the command.
        :param kwargs: Keyword arguments to pass to the command.

        .. todo:: Allow commands to report success or failure
        """
        cmd = self.commands.get(command, None)

        if cmd:
            logging.debug("Executing command '%s' with arguments %r, %r",
                          command, args, kwargs)

            # Workaround for #107 until I'm ready to solve it properly
            winman.update_geometry_cache()

            cmd(winman, *args, **kwargs)

            return True

        logging.error("Unrecognized command: %s", command)
        return False


#: The instance of :class:`CommandRegistry` to be used in 99.9% of use cases.
commands = CommandRegistry()


def cycle_dimensions(winman: WindowManager,
                     win: Wnck.Window,
                     state: Dict[str, Any],
                     *dimensions: Optional[Tuple[float, float, float, float]]
                     ) -> Optional[Rectangle]:
    """Cycle the active window through a list of positions and shapes.

    Takes one step each time this function is called.

    Keeps track of its position by storing the index in an X11 property on
    ``win`` named ``_QUICKTILE_CYCLE_POS``.

    :param dimensions: A list of tuples representing window geometries as
        floating-point values between 0 and 1, inclusive.
    :param win: The window to operate on.
    :returns: The new window dimensions.

    .. todo:: Refactor :func:`cycle_dimensions` to be less of a big pile.
    .. todo:: Consider replacing the ``dimensions`` argument to
        :func:`cycle_dimensions` with a custom type.
    """
    monitor_rect = state['monitor_geom']
    win_rect_rel = Rectangle(*win.get_geometry()).to_relative(monitor_rect)

    logging.debug("Selected preset sequence:\n\t%r", dimensions)

    # Resolve proportional (eg. 0.5) and preserved (None) coordinates
    # TODO: Verify that I didn't break preserved coordinates
    dims = [resolve_fractional_geom(i or win_rect_rel, monitor_rect)
        for i in dimensions]
    if not dims:
        return None

    logging.debug("Selected preset sequence resolves to these monitor-relative"
                  " pixel dimensions:\n\t%r", dims)

    try:
        cmd_idx, pos = winman.get_property(win, '_QUICKTILE_CYCLE_POS',
                                           Xatom.INTEGER)
        logging.debug("Got saved cycle position: %r, %r", cmd_idx, pos)
    except (ValueError, TypeError):  # TODO: Is TypeError still possible?
        logging.debug("Restarting cycle position sequence")
        cmd_idx, pos = None, -1

    if cmd_idx == state.get('cmd_idx', 0):
        pos = (pos + 1) % len(dims)
    else:
        pos = 0

    winman.set_property(win, '_QUICKTILE_CYCLE_POS',
        [int(state.get('cmd_idx', 0)), pos],
        prop_type=Xatom.INTEGER, format_size=32)

    result: Optional[Rectangle] = None
    result = Rectangle(*dims[pos]).from_relative(monitor_rect)

    logging.debug("Target preset is %s relative to monitor %s",
                  result, monitor_rect)

    # If we're overlapping a panel, fall back to a monitor-specific
    # analogue to _NET_WORKAREA to prevent overlapping any panels and
    # risking the WM potentially meddling with the result of resposition()
    test_result = winman.usable_region.clip_to_usable_region(result)
    if test_result != result:
        result = test_result
        logging.debug("Result exceeds usable (non-rectangular) region of "
                      "desktop. (overlapped a non-fullwidth panel?) Reducing "
                      "to within largest usable rectangle: %s", test_result)

    logging.debug("Calling reposition() with default gravity and dimensions "
                  "%r", result)
    winman.reposition(win, result)
    return result


@commands.add('monitor-switch', force_wrap=True)
@commands.add('monitor-next', 1)
@commands.add('monitor-prev', -1)
def cycle_monitors(winman: WindowManager,  # pylint: disable=too-many-arguments
                   win: Wnck.Window,
                   state: Dict[str, Any],
                   step: int = 1,
                   force_wrap: bool = False,
                   n_monitors: Optional[int] = None
                   ) -> None:
    """Cycle the active window between monitors.

    Attempts to preserve each window's position but will ensure that it doesn't
    get placed outside the available space on the target monitor.

    :param win: The window to operate on.
    :param step: How many monitors to step forward or backward.
    :param force_wrap: If :any`True`, this will override setting
        :ref:`MovementsWrap <MovementsWrap>` to :any:`False`.
    """
    old_mon_id, _ = winman.get_monitor(win)
    n_monitors = n_monitors or winman.gdk_screen.get_n_monitors()
    do_wrapping = (state['config'].getboolean('general', 'MovementsWrap') or
                   force_wrap)

    new_mon_id = clamp_idx(old_mon_id + step, n_monitors, do_wrapping)
    new_mon_geom = Rectangle.from_gdk(
        winman.gdk_screen.get_monitor_geometry(new_mon_id))

    # TODO: Unit test this
    new_mon_geom *= winman.gdk_screen.get_monitor_scale_factor(new_mon_id)
    logging.debug("Moving window to monitor %s, which has geometry %s",
                  new_mon_id, new_mon_geom)

    winman.reposition(win, None, new_mon_geom, keep_maximize=True)


@commands.add('monitor-switch-all', force_wrap=True)
@commands.add('monitor-prev-all', -1)
@commands.add('monitor-next-all', 1)
def cycle_monitors_all(
        winman: WindowManager,
        win: Wnck.Window,
        state: Dict[str, Any],
        step: int = 1,
        force_wrap: bool = False
) -> None:
    """Cycle all windows between monitors.

    (Apply :func:`cycle_monitors` to all windows.)

    Attempts to preserve each window's position but will ensure that it doesn't
    get placed outside the available space on the target monitor.

    :param win: The window to operate on.
    :param step: Passed to :func:`cycle_monitors`
    :param force_wrap: Passed to :func:`cycle_monitors`
    """
    # Have to specify types in the description pending a fix for
    # https://github.com/agronholm/sphinx-autodoc-typehints/issues/124

    n_monitors = winman.gdk_screen.get_n_monitors()
    curr_workspace = win.get_workspace()

    if not curr_workspace:
        logging.debug("get_workspace() returned None")
        return

    for window in winman.get_relevant_windows(curr_workspace):
        cycle_monitors(winman, window, state, step, force_wrap, n_monitors)


@commands.add_many({'move-to-{}'.format(name): [variant]
    for name, variant in GravityLayout.GRAVITIES.items()})
def move_to_position(winman: WindowManager,
                     win: Wnck.Window,
                     state: Dict[str, Any],
                     gravity: Gravity,
                     ) -> None:
    """Move the active window to a position on the screen, preserving its
    dimensions.

    :param win: The window to operate on.
    """
    monitor_rect = state['monitor_geom']
    win_rect = Rectangle(*win.get_geometry())

    if gravity == Gravity.CENTER:
        target = win_rect.center_in(monitor_rect)
    else:
        target = Rectangle(
            x=gravity.value[0] * monitor_rect.width,
            y=gravity.value[1] * monitor_rect.height,
            width=win_rect.width,
            height=win_rect.height
        ).from_gravity(gravity).from_relative(monitor_rect)

    # Push it out from under any panels
    logging.debug("Clipping rectangle %r\n\tto usable region %r",
                  target, winman.usable_region)
    confined_target = winman.usable_region.move_to_usable_region(target)

    # Actually reposition the window
    # (and be doubly-sure we're not going to resize it by accident)
    logging.debug("Calling reposition() with dimensions %r", confined_target)
    winman.reposition(win, confined_target, keep_maximize=True,
        geometry_mask=Wnck.WindowMoveResizeMask.X |
                      Wnck.WindowMoveResizeMask.Y)


@commands.add('bordered')
def toggle_decorated(
    winman: WindowManager,
    win: Wnck.Window,
    state: Dict[str, Any]  # pylint: disable=unused-argument
) -> None:
    """Toggle window decoration state on the active window.

    :param win: The window to operate on.
    :param state: Unused
    """
    # Have to specify types in the description pending a fix for
    # https://github.com/agronholm/sphinx-autodoc-typehints/issues/124

    # TODO: Switch to setting this via python-xlib
    display = winman.gdk_screen.get_display()
    win = GdkX11.X11Window.foreign_new_for_display(display, win.get_xid())
    win.set_decorations(Gdk.WMDecoration(0) if win.get_decorations()[1]
        else Gdk.WMDecoration.ALL)


@commands.add('show-desktop', windowless=True)
def toggle_desktop(
        winman: WindowManager,
        win: Wnck.Window,      # pylint: disable=unused-argument
        state: Dict[str, Any]  # pylint: disable=unused-argument
) -> None:
    """Toggle "all windows minimized" to view the desktop.

    :param win: Unused
    :param state: Unused
    """

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
# pylint: disable=too-many-arguments
def toggle_state(
        winman: WindowManager,  # pylint: disable=unused-argument
        win: Wnck.Window,
        state: Dict[str, Any],  # pylint: disable=unused-argument
        command: str,
        check: str,
        takes_bool: bool = False) -> None:
    """Toggle window state on the active window.

    This is an abstraction to unify a bunch of different :class:`Wnck.Window`
    methods behind a common wrapper.

    :param winman: Unused
    :param win: The window to operate on.
    :param state: Unused
    :param command: The method name to be conditionally
        prefixed with ``un``, resolved from ``win``, and called.
    :param check: The method name to be called on ``win`` to check
        whether ``command`` should be prefixed with ``un``.
    :param takes_bool: If :any:`True`, pass :any:`True` or :any:`False` to
        ``check`` rather thank conditionally prefixing it with ``un``
        before resolving.

    .. todo:: When I'm willing to break the external API (command names),
        rename ``vertical-maximize`` and ``horizontal-maximize`` to
        ``maximize-vertical`` and ``maximize-horizontal`` for consistency.
    """
    target = not getattr(win, check)()

    logging.debug("Calling action '%s' with state '%s'", command, target)
    if takes_bool:
        getattr(win, command)(target)
    else:
        getattr(win, ('' if target else 'un') + command)()


@commands.add('trigger-move', 'move')
@commands.add('trigger-resize', 'size')
def trigger_keyboard_action(
        winman: WindowManager,  # pylint: disable=unused-argument
        win: Wnck.Window,
        state: Dict[str, Any],  # pylint: disable=unused-argument
        command: str) -> None:
    """Ask the Window Manager to begin a keyboard-driven operation.

    :param winman: Unused
    :param win: The window to operate on.
    :param state: Unused
    :param command: The string to be appended to ``keyboard_`` and used as a
        method name to look up on ``win``.
    """

    getattr(win, 'keyboard_' + command)()


@commands.add('workspace-go-next', 1, windowless=True)
@commands.add('workspace-go-prev', -1, windowless=True)
@commands.add('workspace-go-up', MotionDirection.UP, windowless=True)
@commands.add('workspace-go-down', MotionDirection.DOWN, windowless=True)
@commands.add('workspace-go-left', MotionDirection.LEFT, windowless=True)
@commands.add('workspace-go-right', MotionDirection.RIGHT, windowless=True)
def workspace_go(
        winman: WindowManager,
        win: Optional[Wnck.Window],  # pylint: disable=unused-argument
        state: Dict[str, Any],
        motion: MotionDirection) -> None:
    """Switch the active workspace.

    (Integer values for ``motion`` may cause wrap-around behaviour depending
    on the value of :ref:`MovementsWrap <MovementsWrap>`.)

    :param state: Used to access the :ref:`MovementsWrap <MovementsWrap>`
        configuration key.
    :param motion: The direction to move the window on the workspace grid or
        the distance to move it by numerical ordering. Accepts
        :class:`Wnck.MotionDirection` or :any:`int`.
    :param win: Unused but required by the command API.
    """
    # Have to specify types in the description pending a fix for
    # https://github.com/agronholm/sphinx-autodoc-typehints/issues/124

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
def workspace_send_window(
        winman: WindowManager,
        win: Wnck.Window,
        state: Dict[str, Any],
        motion: Union[MotionDirection, int]) -> None:
    """Move the active window to another workspace.

    (Integer values for ``motion`` may cause wrap-around behaviour depending
    on the value of :ref:`MovementsWrap <MovementsWrap>`.)

    :param state: Used to access the :ref:`MovementsWrap <MovementsWrap>`
        configuration key.
    :param motion: The direction to move the window on the workspace grid or
        the distance to move it by numerical ordering. Accepts
        :class:`Wnck.MotionDirection` or :any:`int`.
    :param win: The window to operate on.
    """
    # Have to specify types in the description pending a fix for
    # https://github.com/agronholm/sphinx-autodoc-typehints/issues/124

    target = winman.get_workspace(win, motion,
        wrap_around=state['config'].getboolean('general', 'MovementsWrap'))

    if not target:
        # `target` will be None if `win` is pinned or on no workspaces or if
        # there is no workspace matching `motion`.
        return

    win.move_to_workspace(target)


@commands.add('cascade')
def cascade_windows(
        winman: WindowManager,
        win: Wnck.Window,
        state: Dict[str, Any]
) -> None:
    """Cascade all visible windows on the current workspace.

    Arranges windows in a diagonal stair-step pattern starting from the
    top-left of the usable screen area. Each window is offset by 25 pixels
    from the previous one.

    :param winman: The WindowManager instance.
    :param win: The currently active window (used to determine workspace).
    :param state: Command state dictionary.
    """
    curr_workspace = win.get_workspace()
    if not curr_workspace:
        logging.debug("Cannot cascade: no current workspace")
        return

    # Get all relevant windows on the current workspace
    windows = list(winman.get_relevant_windows(curr_workspace))

    if not windows:
        logging.debug("No windows to cascade")
        return

    # Sort windows so active window comes last (appears on top)
    active = winman.screen.get_active_window()
    windows.sort(key=lambda w: 1 if w == active else 0)

    # Get monitor geometry from state (respects panels)
    monitor_geom = state.get('monitor_geom')
    if not monitor_geom:
        logging.debug("No monitor geometry available")
        return

    offset = 25  # pixels

    logging.debug("Cascading %d windows starting at %r",
                  len(windows), monitor_geom)

    for i, window in enumerate(windows):
        # Get current window geometry
        geom = window.get_geometry()
        win_rect = Rectangle(*geom)

        # Calculate cascade position
        new_x = monitor_geom.x + (i * offset)
        new_y = monitor_geom.y + (i * offset)

        # Create target rectangle (preserve original size)
        target = Rectangle(new_x, new_y, win_rect.width, win_rect.height)

        # Make sure window is visible (de-minimize if needed)
        if window.is_minimized():
            window.unminimize(Gdk.CURRENT_TIME)

        # Unshade if shaded
        if window.is_shaded():
            window.unshade()

        logging.debug("Cascading window %r to %r", window, target)

        # Reposition window (unmaximize first if maximized)
        if window.is_maximized():
            window.unmaximize()

        winman.reposition(window, target)


@commands.add('tile-all')
def tile_all_windows(
        winman: WindowManager,
        win: Wnck.Window,
        state: Dict[str, Any]
) -> None:
    """Tile all visible windows in a grid layout.

    Resizes and positions windows to fill the usable screen area in an
    optimal grid arrangement. Grid dimensions are calculated based on
    window count and screen aspect ratio.

    :param winman: The WindowManager instance.
    :param win: The currently active window (used to determine workspace).
    :param state: Command state dictionary.
    """
    curr_workspace = win.get_workspace()
    if not curr_workspace:
        logging.debug("Cannot tile: no current workspace")
        return

    # Get all relevant windows on the current workspace
    windows = list(winman.get_relevant_windows(curr_workspace))

    if not windows:
        logging.debug("No windows to tile")
        return

    n_windows = len(windows)

    # Get monitor geometry from state
    monitor_geom = state.get('monitor_geom')
    if not monitor_geom:
        logging.debug("No monitor geometry available")
        return

    logging.debug("Tiling %d windows in monitor %r",
                  n_windows, monitor_geom)

    # Calculate optimal grid dimensions
    n_cols, n_rows = _calculate_optimal_grid(
        n_windows, monitor_geom.width, monitor_geom.height
    )

    # Calculate base cell dimensions
    cell_width = monitor_geom.width // n_cols
    cell_height = monitor_geom.height // n_rows

    # Position and resize each window
    for i, window in enumerate(windows):
        col = i % n_cols
        row = i // n_cols

        # Calculate position
        x = monitor_geom.x + (col * cell_width)
        y = monitor_geom.y + (row * cell_height)

        # Handle last row (may have fewer windows)
        width = cell_width
        if row == n_rows - 1:
            remaining = n_windows - (row * n_cols)
            if remaining < n_cols and remaining > 0:
                # Expand cells in last row to fill remaining width
                width = monitor_geom.width // remaining
                x = monitor_geom.x + ((i % n_cols) * width)

        height = cell_height

        # Create target rectangle
        target = Rectangle(x, y, width, height)

        # Make sure window is visible
        if window.is_minimized():
            window.unminimize(Gdk.CURRENT_TIME)

        if window.is_shaded():
            window.unshade()

        logging.debug("Tiling window %r to %r", window, target)

        # Unmaximize if maximized, then reposition
        if window.is_maximized():
            window.unmaximize()

        winman.reposition(window, target)


def _calculate_optimal_grid(n: int, width: int, height: int) -> Tuple[int, int]:
    """Calculate optimal grid dimensions for n windows.

    Strategy: Minimize difference from screen aspect ratio while ensuring
    all windows fit (cols * rows >= n).

    :param n: Number of windows.
    :param width: Screen width.
    :param height: Screen height.
    :returns: Tuple of (columns, rows).
    """
    if n <= 1:
        return (1, 1)

    screen_ratio = width / height

    best_cols, best_rows = n, 1
    best_diff = float('inf')

    for cols in range(1, n + 1):
        rows = math.ceil(n / cols)
        cell_ratio = (width / cols) / (height / rows)
        diff = abs(cell_ratio - screen_ratio)

        if diff < best_diff:
            best_diff = diff
            best_cols, best_rows = cols, rows

    return (int(best_cols), int(best_rows))


@commands.add('grid-overlay')
def grid_overlay(
        winman: WindowManager,
        win: Wnck.Window,
        state: Dict[str, Any]
) -> None:
    """Show a grid overlay to visually select window position.

    Allows clicking two corners or using keyboard to select a grid area.
    The active window will be resized to fill the selected area.

    :param winman: The WindowManager instance.
    :param win: The currently active window.
    :param state: Command state dictionary.
    """
    from .overlay import GridOverlay

    # Get monitor geometry
    monitor_id, monitor_geom = winman.get_monitor(win)
    if not monitor_geom:
        logging.debug("No monitor geometry available")
        return

    # Get grid dimensions from config
    config = state.get('config')
    rows = config.getint('general', 'GridRows') if config else 3
    cols = config.getint('general', 'GridCols') if config else 3

    logging.debug("Showing grid overlay: %dx%d on monitor %d",
                  cols, rows, monitor_id)
    logging.debug("Monitor geometry: %s", monitor_geom)

    # Create and show overlay
    overlay = GridOverlay(winman, monitor_geom, rows, cols)
    logging.debug("Overlay created, calling show_overlay()")
    overlay.show_overlay()
    logging.debug("show_overlay() returned")


# vim: set sw=4 sts=4 expandtab :
