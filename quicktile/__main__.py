"""Entry point and related functionality"""

from __future__ import print_function

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

import errno, logging, os, subprocess, sys
from ConfigParser import RawConfigParser

try:
    import pygtk
    pygtk.require('2.0')
except ImportError:
    pass  # Apparently Travis-CI's build environment doesn't add this

import gtk, wnck

from . import gtkexcepthook
gtkexcepthook.enable()

from . import commands, layout
from .util import fmt_table, XInitError
from .version import __version__
from .wm import WindowManager

# Allow MyPy to work without depending on the `typing` package
# (And silence complaints from only using the imported types in comments)
MYPY = False
if MYPY:
    # pylint: disable=unused-import
    from typing import Callable, Dict, Union  # NOQA
del MYPY

#: Location for config files (determined at runtime).
XDG_CONFIG_DIR = os.environ.get('XDG_CONFIG_HOME',
                                os.path.expanduser('~/.config'))

#: Default content for the config file
DEFAULTS = {
    'general': {
        # Use Ctrl+Alt as the default base for key combinations
        'ModMask': '<Ctrl><Alt>',
        'UseWorkarea': True,
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
        "KP_5": "middle",
        "KP_6": "right",
        "KP_7": "top-left",
        "KP_8": "top",
        "KP_9": "top-right",
        "V": "vertical-maximize",
        "H": "horizontal-maximize",
        "C": "move-to-center",
    }
}  # type: Dict[str, Dict[str, Union[str, int, float, bool, None]]]

KEYLOOKUP = {
    ',': 'comma',
    '.': 'period',
    '+': 'plus',
    '-': 'minus',
}  #: Used for resolving certain keysyms


# TODO: Move this to a more appropriate place
wnck.set_client_type(wnck.CLIENT_TYPE_PAGER)  # pylint: disable=no-member

# TODO: Audit all of my TODOs and API docs for accuracy and staleness.

class QuickTileApp(object):
    """The basic Glib application itself."""

    keybinder = None
    dbus_name = None
    dbus_obj = None

    def __init__(self, winman,  # type: WindowManager
                 commands,      # type: commands.CommandRegistry
                 keys=None,     # type: Dict[str, Callable]
                 modmask=None   # type: str
                 ):             # type: (...) -> None
        """Populate the instance variables.

        @param keys: A dict mapping X11 keysyms to L{CommandRegistry}
            command names.
        @param modmask: A modifier mask to prefix to all keybindings.
        @type winman: The L{WindowManager} instance to use.
        @type keys: C{dict}
        """
        self.winman = winman
        self.commands = commands
        self._keys = keys or {}
        self._modmask = modmask or ''

    def run(self):  # type: () -> bool
        """Initialize keybinding and D-Bus if available, then call
        C{gtk.main()}.

        @returns: C{False} if none of the supported backends were available.
        @rtype: C{bool}

        @todo 1.0.0: Retire the C{doCommand} name. (API-breaking change)
        """

        # Attempt to set up the global hotkey support
        try:
            from . import keybinder
        except ImportError:
            logging.error("Could not find python-xlib. Cannot bind keys.")
        else:
            self.keybinder = keybinder.init(
                self._modmask, self._keys, self.commands, self.winman)

        # Attempt to set up the D-Bus API
        try:
            from . import dbus_api
        except ImportError:
            logging.warn("Could not load DBus backend. "
                         "Is python-dbus installed?")
        else:
            self.dbus_name, self.dbus_obj = dbus_api.init(
                self.commands, self.winman)

        # If either persistent backend loaded, start the GTK main loop.
        if self.keybinder or self.dbus_obj:
            try:
                gtk.main()  # pylint: disable=no-member
            except KeyboardInterrupt:
                pass
            return True
        else:
            return False

    def show_binds(self):  # type: () -> None
        """Print a formatted readout of defined keybindings and the modifier
        mask to stdout.

        @todo: Look into moving this into L{KeyBinder}
        """

        print("Keybindings defined for use with --daemonize:\n")
        print("Modifier: %s\n" % (self._modmask or '(none)'))
        print(fmt_table(self._keys, ('Key', 'Action')))

def attach_glib_log_filter():
    """Attach a copy of grep to our stderr to filter out _OB_WM errors.

    Hook up grep to filter out spurious libwnck error messages that we
    can't filter properly because PyGTK doesn't expose g_log_set_handler()
    """
    glib_log_filter = subprocess.Popen(
            ['grep', '-v', 'Unhandled action type _OB_WM'],
            stdin=subprocess.PIPE)

    # Redirect stderr through grep
    if not glib_log_filter.stdin:
        raise AssertionError("Did not receive stdin for log filter")
    os.dup2(glib_log_filter.stdin.fileno(), sys.stderr.fileno())

def load_config(path):  # type: (str) -> RawConfigParser
    """Load the config file from the given path, applying fixes as needed.

    @todo: Refactor all this
    """
    first_run = not os.path.exists(path)

    config = RawConfigParser()

    # Make keys case-sensitive because keysyms must be
    config.optionxform = str  # type: ignore # (Cannot assign to a method)

    # TODO: Maybe switch to two config files so I can have only the keys in the
    #       keymap case-sensitive?
    config.read(path)
    dirty = False

    if not config.has_section('general'):
        config.add_section('general')
        # Change this if you make backwards-incompatible changes to the
        # section and key naming in the config file.
        config.set('general', 'cfg_schema', 1)
        dirty = True

    for key, val in DEFAULTS['general'].items():
        if not config.has_option('general', key):
            config.set('general', key, str(val))
            dirty = True

    mk_raw = modkeys = config.get('general', 'ModMask')
    if ' ' in modkeys.strip() and '<' not in modkeys:
        modkeys = '<%s>' % '><'.join(modkeys.strip().split())
        logging.info("Updating modkeys format:\n %r --> %r", mk_raw, modkeys)
        config.set('general', 'ModMask', modkeys)
        dirty = True

    # Either load the keybindings or use and save the defaults
    if config.has_section('keys'):
        keymap = dict(config.items('keys'))
    else:
        keymap = DEFAULTS['keys']
        config.add_section('keys')
        for row in keymap.items():
            config.set('keys', row[0], row[1])
        dirty = True

    # Migrate from the deprecated syntax for punctuation keysyms
    for key in keymap:
        # Look up unrecognized shortkeys in a hardcoded dict and
        # replace with valid names like ',' -> 'comma'
        if key in KEYLOOKUP:
            logging.warn("Updating config file from deprecated keybind syntax:"
                    "\n\t%r --> %r", key, KEYLOOKUP[key])
            config.remove_option('keys', key)
            config.set('keys', KEYLOOKUP[key], keymap[key])
            dirty = True

    if dirty:
        cfg_file = open(path, 'wb')

        # TODO: REPORT: Argument 1 to "write" of "RawConfigParser" has
        #               incompatible type BinaryIO"; expected "file"
        config.write(cfg_file)  # type: ignore

        cfg_file.close()
        if first_run:
            logging.info("Wrote default config file to %s", path)

    return config

def main():  # type: () -> None
    """setuptools entry point"""
    # TODO: Switch to argparse
    from optparse import OptionParser, OptionGroup
    parser = OptionParser(usage="%prog [options] [action] ...",
            version="%%prog v%s" % __version__)
    parser.add_option('-d', '--daemonize', action="store_true",
        dest="daemonize", default=False, help="Attempt to set up global "
        "keybindings using python-xlib and a D-Bus service using dbus-python. "
        "Exit if neither succeeds")
    parser.add_option('-b', '--bindkeys', action="store_true",
        dest="daemonize", default=False,
        help="Deprecated alias for --daemonize")
    parser.add_option('--debug', action="store_true", dest="debug",
        default=False, help="Display debug messages")
    parser.add_option('--no-workarea', action="store_true", dest="no_workarea",
        default=False, help="Overlap panels but work better with "
        "non-rectangular desktops")

    help_group = OptionGroup(parser, "Additional Help")
    help_group.add_option('--show-bindings', action="store_true",
        dest="show_binds", default=False, help="List all configured keybinds")
    help_group.add_option('--show-actions', action="store_true",
        dest="show_args", default=False, help="List valid arguments for use "
        "without --daemonize")
    parser.add_option_group(help_group)

    opts, args = parser.parse_args()

    if not opts.debug:
        attach_glib_log_filter()

    # Set up the output verbosity
    logging.basicConfig(level=logging.DEBUG if opts.debug else logging.INFO,
                        format='%(levelname)s: %(message)s')

    cfg_path = os.path.join(XDG_CONFIG_DIR, 'quicktile.cfg')
    first_run = not os.path.exists(cfg_path)
    config = load_config(cfg_path)

    ignore_workarea = ((not config.getboolean('general', 'UseWorkarea')) or
                       opts.no_workarea)

    # TODO: Rearchitect so this hack isn't needed
    commands.cycle_dimensions = commands.commands.add_many(
        layout.make_winsplit_positions(config.getint('general', 'ColumnCount'))
    )(commands.cycle_dimensions)
    commands.commands.extra_state = {'config': config}

    try:
        winman = WindowManager(ignore_workarea=ignore_workarea)
    except XInitError as err:
        logging.critical("%s", err)
        sys.exit(1)
    app = QuickTileApp(winman,
                       commands.commands,
                       keys=dict(config.items('keys')),
                       modmask=config.get('general', 'ModMask'))

    if opts.show_binds:
        app.show_binds()
    if opts.show_args:
        print(commands.commands)

    if opts.daemonize:
        if not app.run():
            logging.critical("Neither the Xlib nor the D-Bus backends were "
                             "available")
            sys.exit(errno.ENOENT)
            # FIXME: What's the proper exit code for "library not found"?
    elif not first_run:
        if args:
            winman.screen.force_update()

            for arg in args:
                commands.commands.call_multiple(arg, winman)
            while gtk.events_pending():  # pylint: disable=no-member
                gtk.main_iteration()  # pylint: disable=no-member
        elif not opts.show_args and not opts.show_binds:
            print(commands.commands)
            print("\nUse --help for a list of valid options.")
            sys.exit(errno.ENOENT)

if __name__ == '__main__':
    main()

# vim: set sw=4 sts=4 expandtab :
