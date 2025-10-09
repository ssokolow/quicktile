"""Entry point and main loop

.. todo::
 - Audit all of my in-code TODOs for accuracy and staleness.
 - Move :func:`Wnck.set_client_type` call to a more appropriate place
   (:mod:`quicktile.wm`?)
 - Complete the automated test suite.
 - Finish refactoring the code to be cleaner and more maintainable.
 - Reconsider use of the name
   `-\\-daemonize <../cli.html#cmdoption-quicktile-d>`_. That tends to imply
   self-backgrounding.
 - Decide whether to replace `python-xlib`_ with `xcffib`_
   (the Python equivalent to ``libxcb``). On the one hand, python-xlib looks
   like it'd probably be easier to write an :file:`objects.inv` for at first
   glance. On the other hand, `xcffib`_ binds to the newer XCB API.
 - Implement the secondary major features of WinSplit Revolution (eg.
   process-shape associations, locking/welding window edges, etc.)
 - Consider rewriting :func:`quicktile.commands.cycle_dimensions` to allow
   command-line use to jump to a specific index without actually flickering the
   window through all the intermediate shapes.

.. _python-xlib: https://pypi.org/project/python-xlib/
.. _xcffib: https://pypi.org/project/xcffib/
"""

from __future__ import print_function

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

# Silence PyLint being flat-out wrong about MyPy type annotations and
# complaining about my grouped imports
# pylint: disable=unsubscriptable-object
# pylint: disable=wrong-import-order

import errno, logging, os, signal, sys
from argparse import ArgumentParser
from importlib.resources import files

from Xlib.display import Display as XDisplay
from Xlib.error import DisplayConnectionError

import gi
gi.require_version('GLib', '2.0')
gi.require_version('Gtk', '3.0')
gi.require_version('Wnck', '3.0')
from gi.repository import GLib, Gtk, Wnck

from . import commands, gtkexcepthook, layout
from .config import load_config, XDG_CONFIG_DIR
from .util import fmt_table, XInitError
from .wm import WindowManager

# -- Type-Annotation Imports --
from typing import Dict
from typing import Optional  # NOQA pylint: disable=unused-import
# --

__version__ = files("quicktile").joinpath("VERSION").read_text().strip()

Wnck.set_client_type(Wnck.ClientType.PAGER)


class QuickTileApp:
    """The basic Glib application itself.

    :param commands: The command registry to use to resolve command names.
    :param keys: A dict mapping :func:`Gtk.accelerator_parse` strings to
        command names.
    :param modmask: A modifier mask to prepend to all ``keys``.
    :param winman: The window manager to invoke commands with so they can act.
    """

    def __init__(self, winman: WindowManager,
                 commands: commands.CommandRegistry,
                 keys: Dict[str, str],
                 modmask: str = '',
                 ):
        self.winman = winman
        self.commands = commands
        self._keys = keys or {}
        self._modmask = modmask or ''

    def run(self) -> bool:
        """Initialize keybinding and D-Bus if available, then call
        :func:`Gtk.main`.

        :returns: :any:`False` if none of the supported backends
            were available.
        """

        # Attempt to set up the global hotkey support
        try:
            from . import keybinder  # pylint: disable=C0415
            o_keybinder: Optional[keybinder.KeyBinder] = keybinder.init(
                self._modmask, self._keys, self.commands, self.winman)
        except ImportError:  # pragma: nocover
            o_keybinder = None
            logging.error("Could not find python-xlib. Cannot bind keys.")

        # Attempt to set up the D-Bus API
        try:
            from . import dbus_api  # pylint: disable=C0415
        except ImportError:  # pragma: nocover
            dbus_result = None
            logging.warning("Could not load DBus backend. "
                            "Is python-dbus installed?")
        else:
            dbus_result = dbus_api.init(self.commands, self.winman)

        # If either persistent backend loaded, start the GTK main loop.
        if o_keybinder or dbus_result:
            try:
                Gtk.main()
            except KeyboardInterrupt:
                pass
            return True
        return False

    def show_binds(self) -> None:
        """Print a formatted readout of defined keybindings and the modifier
        mask to stdout.

        .. todo:: Look into moving this keybind pretty-printing into
            :class:`quicktile.keybinder.KeyBinder`
        """

        print("Keybindings defined for use with --daemonize:\n")
        print("Modifier: %s\n" % (self._modmask or '(none)'))
        print(fmt_table(self._keys, ('Key', 'Action')))


def wnck_log_filter(domain: str, level: GLib.LogLevelFlags,
        message: str, userdata: object = None):
    """A custom function for :func:`GLib.log_set_handler` which filters out
    the spurious error about ``_OB_WM_ACTION_UNDECORATE`` being un-handled.

    :param domain: The logging domain. Should be ``Wnck``.
    :param level: The logging level Should be
        :py:attr:`GLib.LogLevelFlags.LEVEL_WARNING`.
    :param message: The error message
    :param userdata: Required by the API but unused.
    """

    if '_OB_WM_ACTION_UNDECORATE' not in message:
        # The "or 0" works around a bug where it's documented as accepting
        # `object` or `None` and says `None` is one of the only valid values
        # if you try to pass `{}`, but it refuses to accept `None`.
        GLib.log_default_handler(domain, level, message, userdata or 0)


def argparser() -> ArgumentParser:
    """:class:`argparse.ArgumentParser` definition that is compatible with
        `sphinxcontrib.autoprogram
        <https://sphinxcontrib-autoprogram.readthedocs.io/en/stable/>`_"""
    parser = ArgumentParser(prog='QuickTile',
        description='Add tiling hotkeys to X11-based desktops')
    parser.add_argument('-V', '--version', action='version',
            version="%%(prog)s v%s" % __version__)
    parser.add_argument('-d', '--daemonize', action="store_true",
        default=False, help="Attempt to set up global "
        "keybindings using python-xlib and a D-Bus service using dbus-python. "
        "Exit if neither succeeds.")
    parser.add_argument('-b', '--bindkeys', action="store_true",
        dest="daemonize", default=False, help="Old alias for --daemonize from "
        "before it also did D-Bus")
    parser.add_argument('--debug', action="store_true", default=False,
        help="Display debug messages")
    parser.add_argument('--no-excepthook', action="store_true",
        default=False, help="Disable the error-handling dialog to allow for "
        "more reliable use in unattended scripting")
    parser.add_argument('--no-workarea', action="store_true",
        default=False, help="No effect. Retained for compatibility.")
    parser.add_argument('command', action="store", nargs="*",
        help="Window-tiling command to execute")

    help_group = parser.add_argument_group("Additional Help")
    help_group.add_argument('--show-bindings', action="store_true",
        default=False, help="List all configured keybinds")
    help_group.add_argument('--show-actions', action="store_true",
        default=False, help="List valid arguments for use without --daemonize")

    return parser


def main() -> None:
    """setuptools-compatible entry point

    :raises XInitError: Failed to connect to the X server.

    .. todo:: :func:`quicktile.__main__.main` is an overly complex blob and
        needs to be refactored.
    .. todo:: Rearchitect so the hack with registering
        :func:`quicktile.commands.cycle_dimensions` inside
        :func:`quicktile.__main__.main` isn't necessary.
    .. todo:: Rework ``python-xlib`` failure model so QuickTile will know to
        exit if all keybinding attempts failed and D-Bus also couldn't
        be bound.
    """
    parser = argparser()
    args = parser.parse_args()

    # Set up the output verbosity
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format='%(levelname)s: %(message)s')

    cfg_path = os.path.join(XDG_CONFIG_DIR, 'quicktile.cfg')
    first_run = not os.path.exists(cfg_path)
    config = load_config(cfg_path)

    commands.cycle_dimensions = commands.commands.add_many(
        layout.make_winsplit_positions(
            config.getint('general', 'ColumnCount'),
            config.getfloat('general', 'MarginX_Percent') / 100,
            config.getfloat('general', 'MarginY_Percent') / 100
        )
    )(commands.cycle_dimensions)
    commands.commands.extra_state = {'config': config}

    GLib.log_set_handler('Wnck', GLib.LogLevelFlags.LEVEL_WARNING,
        wnck_log_filter)

    if not args.no_excepthook:
        gtkexcepthook.enable()

    try:
        x_display = XDisplay()
    except (UnicodeDecodeError, DisplayConnectionError) as err:
        raise XInitError("python-xlib failed with %s when asked to open"
                        " a connection to the X server. Cannot bind keys."
                        "\n\tIt's unclear why this happens, but it is"
                        " usually fixed by deleting your ~/.Xauthority"
                        " file and rebooting."
                        % err.__class__.__name__)

    # Work around a "the Gtk.Application ::startup handler does it for you" bug
    if not Gtk.init_check():
        raise XInitError("Gtk failed to connect to the X server. Exiting.")

    try:
        winman = WindowManager(x_display=x_display)
    except XInitError as err:
        logging.critical("%s", err)
        sys.exit(1)

    app = QuickTileApp(winman,
                       commands.commands,
                       keys=dict(config.items('keys')),
                       modmask=config.get('general', 'ModMask'))

    if args.show_bindings:
        app.show_binds()
    if args.show_actions:
        print(commands.commands)

    if args.daemonize:
        # Restore PyGTK-like Ctrl+C behaviour for easy development
        signal.signal(signal.SIGINT, signal.SIG_DFL)

        if not app.run():
            logging.critical("Neither the Xlib nor the D-Bus backends were "
                             "available")
            sys.exit(errno.ELIBACC)
    elif not first_run:
        if args:
            winman.screen.force_update()

            for arg in args.command:
                commands.commands.call(arg, winman)
            while Gtk.events_pending():
                Gtk.main_iteration()
        elif not args.show_actions and not args.show_bindings:
            print(commands.commands)
            print("\nUse --help for a list of valid options.")
            sys.exit(errno.ENOENT)


if __name__ == '__main__':
    main()

# vim: set sw=4 sts=4 expandtab :
