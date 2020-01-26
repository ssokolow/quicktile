"""Entry point, configuration parser, and main loop

.. todo::
 - Audit all of my TODOs and API docs for accuracy and staleness.
 - Move :func:`Wnck.set_client_type` call to a more appropriate place
   (:mod:`quicktile.wm`?)
 - Complete the automated test suite.
 - Finish refactoring the code to be cleaner and more maintainable.
 - Reconsider use of the name ``--daemonize``. That tends to imply
   self-backgrounding.
 - Decide whether to replace `python-xlib`_ with `xcffib`_
   (the Python equivalent to ``libxcb``).
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
from configparser import ConfigParser

from Xlib.display import Display as XDisplay
from Xlib.error import DisplayConnectionError

import gi
gi.require_version('GLib', '2.0')
gi.require_version('Gtk', '3.0')
gi.require_version('Wnck', '3.0')
from gi.repository import GLib, Gtk, Wnck

from . import commands, layout
from .util import fmt_table, XInitError
from .version import __version__
from .wm import WindowManager

# -- Type-Annotation Imports --
from typing import Dict, Union
from typing import Optional  # NOQA pylint: disable=unused-import

#: MyPy type alias for fields loaded from config files
CfgDict = Dict[str, Union[str, int, float, bool, None]]  # pylint:disable=C0103
# --

#: Location for config files (determined at runtime).
XDG_CONFIG_DIR = os.environ.get('XDG_CONFIG_HOME',
                                os.path.expanduser('~/.config'))

#: Default content for the configuration file
#:
#: .. todo:: Figure out a way to show :data:`DEFAULTS` documentation but with
#:    the structure pretty-printed.
DEFAULTS = {
    'general': {
        # Use Ctrl+Alt as the default base for key combinations
        'ModMask': '<Ctrl><Alt>',
        'MovementsWrap': True,
        'ColumnCount': 3
    },
    'keys': {
        "KP_Enter": "monitor-switch",
        "KP_0": "maximize",
        "KP_1": "bottom-left",
        "KP_2": "bottom",
        "KP_3": "bottom-right",
        "KP_4": "left",
        "KP_5": "center",
        "KP_6": "right",
        "KP_7": "top-left",
        "KP_8": "top",
        "KP_9": "top-right",
        "<Shift>KP_1": "move-to-bottom-left",
        "<Shift>KP_2": "move-to-bottom",
        "<Shift>KP_3": "move-to-bottom-right",
        "<Shift>KP_4": "move-to-left",
        "<Shift>KP_5": "move-to-center",
        "<Shift>KP_6": "move-to-right",
        "<Shift>KP_7": "move-to-top-left",
        "<Shift>KP_8": "move-to-top",
        "<Shift>KP_9": "move-to-top-right",
        "V": "vertical-maximize",
        "H": "horizontal-maximize",
        "C": "move-to-center",
    }
}  # type: Dict[str, CfgDict]

#: Used for resolving certain keysyms
#:
#: .. todo:: Figure out how to replace :data:`KEYLOOKUP` with a fallback that
#:      uses something in `Gtk <http://lazka.github.io/pgi-docs/Gtk-3.0/>`_ or
#:      ``python-xlib`` to look up the keysym from the character it types.
KEYLOOKUP = {
    ',': 'comma',
    '.': 'period',
    '+': 'plus',
    '-': 'minus',
}

Wnck.set_client_type(Wnck.ClientType.PAGER)


class QuickTileApp(object):
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
                 modmask: str='',
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
            from . import keybinder
        except ImportError:
            o_keybinder = None  # type: Optional[keybinder.KeyBinder]
            logging.error("Could not find python-xlib. Cannot bind keys.")
        else:
            o_keybinder = keybinder.init(
                self._modmask, self._keys, self.commands, self.winman)

        # Attempt to set up the D-Bus API
        try:
            from . import dbus_api
        except ImportError:
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
        else:
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


def load_config(path) -> ConfigParser:
    """Load the config file from the given path, applying fixes as needed.
    If it does not exist, create it from the configuration defaults.

    :param path: The path to load or initialize.

    :raises TypeError: Raised if the keys or values in the :ref:`[keys]`
        section of the configuration file or what they resolve to via
        :any:`KEYLOOKUP` are not :any:`str` instances.

    .. todo:: Refactor config parsing. It's an ugly blob.
    """
    first_run = not os.path.exists(path)

    config = ConfigParser(interpolation=None)

    # Make keys case-sensitive because keysyms must be
    #
    # (``type: ignore`` to squash a false positive for something the Python 3.x
    # documentation specifically *recommends* over using RawConfigParser)
    config.optionxform = str  # type: ignore

    config.read(path)
    dirty = False

    if not config.has_section('general'):
        config.add_section('general')
        # Change this if you make backwards-incompatible changes to the
        # section and key naming in the config file.
        config.set('general', 'cfg_schema', '1')
        dirty = True

    for key, val in DEFAULTS['general'].items():
        if not config.has_option('general', key):
            config.set('general', key, str(val))
            dirty = True

    mk_raw = config.get('general', 'ModMask')
    modkeys = mk_raw.strip()  # pylint: disable=E1101
    if ' ' in modkeys and '<' not in modkeys:
        modkeys = '<%s>' % '><'.join(modkeys.split())
        logging.info("Updating modkeys format:\n %r --> %r", mk_raw, modkeys)
        config.set('general', 'ModMask', modkeys)
        dirty = True

    # Either load the keybindings or use and save the defaults
    if config.has_section('keys'):
        keymap = dict(config.items('keys'))  # type: CfgDict
    else:
        keymap = DEFAULTS['keys']
        config.add_section('keys')
        for key, cmd in keymap.items():
            if not isinstance(key, str):
                raise TypeError("Hotkey name must be a str: {!r}".format(key))
            if not isinstance(cmd, str):
                raise TypeError("Command name must be a str: {!r}".format(cmd))
            config.set('keys', key, cmd)
        dirty = True

    # Migrate from the deprecated syntax for punctuation keysyms
    for key in keymap:
        # Look up unrecognized shortkeys in a hardcoded dict and
        # replace with valid names like ',' -> 'comma'
        if key in KEYLOOKUP:
            cmd = keymap[key]
            if not isinstance(cmd, str):
                raise TypeError("Command name must be a str: {!r}".format(cmd))

            logging.warning("Updating config file from deprecated keybind "
                "syntax:\n\t%r --> %r", key, KEYLOOKUP[key])
            config.remove_option('keys', key)
            config.set('keys', KEYLOOKUP[key], cmd)
            dirty = True

    # Automatically update the old 'middle' command to 'center'
    for key in keymap:
        if keymap[key] == 'middle':
            keymap[key] = cmd = 'center'
            logging.warning("Updating old command in config file:"
                    "\n\tmiddle --> center")
            config.set('keys', key, cmd)
            dirty = True

    if dirty:
        with open(path, 'w') as cfg_file:
            config.write(cfg_file)
        if first_run:
            logging.info("Wrote default config file to %s", path)

    return config


def wnck_log_filter(domain: str, level: GLib.LogLevelFlags,
        message: str, userdata: object=None):
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
    parser = ArgumentParser(description='Window Tiling addon for X11-based '
        'desktops')
    parser.add_argument('-V', '--version', action='version',
            version="%%(prog)s v%s" % __version__)
    parser.add_argument('-d', '--daemonize', action="store_true",
        default=False, help="Attempt to set up global "
        "keybindings using python-xlib and a D-Bus service using dbus-python. "
        "Exit if neither succeeds.")
    parser.add_argument('-b', '--bindkeys', action="store_true",
        dest="daemonize", default=False, help="Old alias for --daemonize")
    parser.add_argument('--debug', action="store_true", default=False,
        help="Display debug messages")
    parser.add_argument('--no-excepthook', action="store_true",
        default=False, help="Disable the error-handling dialog to allow for "
        "use in unattended scripting.")
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
    .. todo:: Rework python-xlib failure model so QuickTile will know to exit
        if all keybinding attempts failed and D-Bus also couldn't be bound.
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
        layout.make_winsplit_positions(config.getint('general', 'ColumnCount'))
    )(commands.cycle_dimensions)
    commands.commands.extra_state = {'config': config}

    GLib.log_set_handler('Wnck', GLib.LogLevelFlags.LEVEL_WARNING,
        wnck_log_filter)

    from . import gtkexcepthook
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
