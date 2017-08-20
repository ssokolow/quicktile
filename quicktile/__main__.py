"""Entry point and related functionality"""

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

import gtkexcepthook
gtkexcepthook.enable()

from . import commands, layout
from .util import fmt_table, XInitError
from .version import __version__
from .wm import WindowManager

#: Location for config files (determined at runtime).
XDG_CONFIG_DIR = os.environ.get('XDG_CONFIG_HOME',
                                os.path.expanduser('~/.config'))

#: Default content for the config file
DEFAULTS = {
    'general': {
        # Use Ctrl+Alt as the default base for key combinations
        'ModMask': '<Ctrl><Alt>',
        'UseWorkarea': True,
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
}

KEYLOOKUP = {
    ',': 'comma',
    '.': 'period',
    '+': 'plus',
    '-': 'minus',
}  #: Used for resolving certain keysyms


wnck.set_client_type(wnck.CLIENT_TYPE_PAGER)  # pylint: disable=no-member

class QuickTileApp(object):
    """The basic Glib application itself."""

    keybinder = None
    dbus_name = None
    dbus_obj = None

    def __init__(self, winman, commands, keys=None, modmask=None):
        """Populate the instance variables.

        @param keys: A dict mapping X11 keysyms to L{CommandRegistry}
            command names.
        @param modmask: A modifier mask to prefix to all keybindings.
        @type winman: The L{WindowManager} instance to use.
        @type keys: C{dict}
        @type modmask: C{GdkModifierType}
        """
        self.winman = winman
        self.commands = commands
        self._keys = keys or {}
        self._modmask = modmask or gtk.gdk.ModifierType(0)

    def run(self):
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

    def show_binds(self):
        """Print a formatted readout of defined keybindings and the modifier
        mask to stdout.

        @todo: Look into moving this into L{KeyBinder}
        """

        print "Keybindings defined for use with --daemonize:\n"
        print "Modifier: %s\n" % self._modmask
        print fmt_table(self._keys, ('Key', 'Action'))

def main():
    """setuptools entry point"""
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

    # Hook up grep to filter out spurious libwnck error messages that we
    # can't filter properly because PyGTK doesn't expose g_log_set_handler()
    if not opts.debug:
        glib_log_filter = subprocess.Popen(
                ['grep', '-v', 'Unhandled action type _OB_WM'],
                stdin=subprocess.PIPE)

        # Redirect stderr through grep
        os.dup2(glib_log_filter.stdin.fileno(), sys.stderr.fileno())

    # Set up the output verbosity
    logging.basicConfig(level=logging.DEBUG if opts.debug else logging.INFO,
                        format='%(levelname)s: %(message)s')

    # Load the config from file if present
    # TODO: Refactor all this
    cfg_path = os.path.join(XDG_CONFIG_DIR, 'quicktile.cfg')
    first_run = not os.path.exists(cfg_path)

    config = RawConfigParser()
    config.optionxform = str  # Make keys case-sensitive
    # TODO: Maybe switch to two config files so I can have only the keys in the
    #       keymap case-sensitive?
    config.read(cfg_path)
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
        transKey = key
        if key in KEYLOOKUP:
            logging.warn("Updating config file from deprecated keybind syntax:"
                    "\n\t%r --> %r", key, KEYLOOKUP[key])
            transKey = KEYLOOKUP[key]
            dirty = True

    if dirty:
        cfg_file = file(cfg_path, 'wb')
        config.write(cfg_file)
        cfg_file.close()
        if first_run:
            logging.info("Wrote default config file to %s", cfg_path)

    ignore_workarea = ((not config.getboolean('general', 'UseWorkarea')) or
                       opts.no_workarea)

    # TODO: Rearchitect so this hack isn't needed
    commands.cycle_dimensions = commands.commands.add_many(
        layout.make_winsplit_positions(config.getint('general', 'ColumnCount'))
    )(commands.cycle_dimensions)

    try:
        winman = WindowManager(ignore_workarea=ignore_workarea)
    except XInitError as err:
        logging.critical(err)
        sys.exit(1)
    app = QuickTileApp(winman, commands.commands, keymap, modmask=modkeys)

    if opts.show_binds:
        app.show_binds()
    if opts.show_args:
        print commands.commands

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
                commands.commands.call(arg, winman)
            while gtk.events_pending():  # pylint: disable=no-member
                gtk.main_iteration()  # pylint: disable=no-member
        elif not opts.show_args and not opts.show_binds:
            print commands.commands
            print "\nUse --help for a list of valid options."
            sys.exit(errno.ENOENT)

if __name__ == '__main__':
    main()

# vim: set sw=4 sts=4 expandtab :
