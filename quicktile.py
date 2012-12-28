#!/bin/sh
"""":
python2 -c "" 2>/dev/null && exec python2 $0 ${1+"$@"}
python -c "" 2>/dev/null && exec python $0 ${1+"$@"}
echo "Could not find a python interpreter."
exit 1
"""
# -*- coding: utf-8 -*-
"""QuickTile, a WinSplit clone for X11 desktops

Thanks to Thomas Vander Stichele for some of the documentation cleanups.

@bug: The toggleMaximize function powering the "maximize" action can't unmaximize.
      (Workaround: Use one of the regular tiling actions to unmaximize)

@todo:
 - Reconsider use of --daemonize. That tends to imply self-backgrounding.
 - See about de-duplicating "This temporary hack prevents an Exception with MPlayer."
 - Look into supporting xpyb (the Python equivalent to libxcb) for global
   keybinding.
 - Clean up the code. It's functional, but an ugly rush-job.
 - Decide how to handle maximization and stick with it.
 - Implement the secondary major features of WinSplit Revolution (eg.
   process-shape associations, locking/welding window edges, etc.)
 - Consider rewriting cycleDimensions to allow command-line use to jump to a
   specific index without actually flickering the window through all the
   intermediate shapes.
 - Can I hook into the GNOME and KDE keybinding APIs without using PyKDE or
   gnome-python? (eg. using D-Bus, perhaps?)

@todo: Merge remaining appropriate portions of:
 - https://thomas.apestaart.org/thomas/trac/changeset/1123/patches/quicktile/quicktile.py
 - https://thomas.apestaart.org/thomas/trac/changeset/1122/patches/quicktile/quicktile.py
 - https://thomas.apestaart.org/thomas/trac/browser/patches/quicktile/README

References and code used:
 - http://faq.pygtk.org/index.py?req=show&file=faq23.017.htp
 - http://faq.pygtk.org/index.py?req=show&file=faq23.039.htp
 - http://www.larsen-b.com/Article/184.html
 - http://www.pygtk.org/pygtk2tutorial/sec-MonitoringIO.html

@newfield appname: Application Name
"""

__appname__ = "QuickTile"
__author__  = "Stephan Sokolow (deitarion/SSokolow)"
__version__ = "0.1.5"
__license__ = "GNU GPL 2.0 or later"

import pygtk
pygtk.require('2.0')

import errno, gtk, gobject, operator, logging, os, sys
from ConfigParser import RawConfigParser
from heapq import heappop, heappush
from itertools import chain, combinations

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

try:
    from Xlib import X
    from Xlib.display import Display
    from Xlib.error import BadAccess
    from Xlib.XK import string_to_keysym
    XLIB_PRESENT = True #: Indicates whether python-xlib was found
except ImportError:
    XLIB_PRESENT = False #: Indicates whether python-xlib was found

DBUS_PRESENT = False
try:
    import dbus.service
    from dbus import SessionBus
    from dbus.exceptions import DBusException
    from dbus.mainloop.glib import DBusGMainLoop
except ImportError:
    pass
else:
    try:
        DBusGMainLoop(set_as_default=True)
        sessBus = SessionBus()
    except DBusException:
        pass
    else:
        DBUS_PRESENT = True

XDG_CONFIG_DIR = os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))

#TODO: Figure out how best to put this in the config file.
POSITIONS = {
    'left'           : (
        (0,         0,   0.5,       1),
        (0,         0,   1.0/3,     1),
        (0,         0,   1.0/3 * 2, 1)
    ),
    'middle'         : (
        (0,         0,   1,         1),
        (1.0/3,     0,   1.0/3,     1),
        (1.0/6,     0,   1.0/3 * 2, 1)
    ),
    'right'          : (
        (0.5,       0,   0.5,       1),
        (1.0/3 * 2, 0,   1.0/3,     1),
        (1.0/3,     0,   1.0/3 * 2, 1)
    ),
    'top'            : (
        (0,         0,   1,         0.5),
        (1.0/3,     0,   1.0/3,     0.5)
    ),
    'bottom'         : (
        (0,         0.5, 1,         0.5),
        (1.0/3,     0.5, 1.0/3,     0.5)
    ),
    'top-left'       : (
        (0,         0,   0.5,       0.5),
        (0,         0,   1.0/3,     0.5),
        (0,         0,   1.0/3 * 2, 0.5)
    ),
    'top-right'      : (
        (0.5,       0,   0.5,       0.5),
        (1.0/3 * 2, 0,   1.0/3,     0.5),
        (1.0/3,     0,   1.0/3 * 2, 0.5)
    ),
    'bottom-left'    : (
        (0,         0.5, 0.5,       0.5),
        (0,         0.5, 1.0/3,     0.5),
        (0,         0.5, 1.0/3 * 2, 0.5)
    ),
    'bottom-right'   : (
        (0.5,       0.5, 0.5,       0.5),
        (1.0/3 * 2, 0.5, 1.0/3,     0.5),
        (1.0/3,     0.5, 1.0/3 * 2, 0.5)
    ),
    'maximize'            : 'toggleMaximize',
    'monitor-switch'      : 'cycleMonitors',
    'vertical-maximize'   : ((None,      0,   None,      1),),
    'horizontal-maximize' : ((0,      None,   1,      None),),
    'move-to-center'      : 'moveCenter',
} #: command-to-action mappings

#NOTE: For keysyms outside the latin1 and miscellany groups, you must first
#      call C{Xlib.XK.load_keysym_group()} with the name (minus extension) of
#      the appropriate module in site-packages/Xlib/keysymdef/*.py
#TODO: Implement a LoadExtraKeysyms config key to support this.
DEFAULTS = {
    'general': {
        # Use Ctrl+Alt as the default base for key combinations
        'ModMask': 'Control Mod1',
        'UseWorkarea': True,
    },
    'keys': {
        "KP_0"     : "maximize",
        "KP_1"     : "bottom-left",
        "KP_2"     : "bottom",
        "KP_3"     : "bottom-right",
        "KP_4"     : "left",
        "KP_5"     : "middle",
        "KP_6"     : "right",
        "KP_7"     : "top-left",
        "KP_8"     : "top",
        "KP_9"     : "top-right",
        "KP_Enter" : "monitor-switch",
        "V"        : "vertical-maximize",
        "H"        : "horizontal-maximize",
        "C"        : "move-to-center",
    }
} #: Default content for the config file

KEYLOOKUP = {
    ',' : 'comma',
    '.' : 'period',
    '+' : 'plus',
    '-' : 'minus',
}

def powerset(iterable):
    "powerset([1,2,3]) --> () (1,) (2,) (3,) (1,2) (1,3) (2,3) (1,2,3)"
    s = list(iterable)
    return chain.from_iterable(combinations(s, r) for r in range(len(s) + 1))

class DependencyError(Exception):
    """Raised when a required dependency is missing."""
    pass

class WindowManager(object):
    """A simple API-wrapper class for manipulating window positioning."""
    def __init__(self, commands, screen=None, ignore_workarea=False):
        """
        Initializes WindowManager.

        @param screen: The X11 screen to operate on. If C{None}, the default
            screen as retrieved by C{gtk.gdk.screen_get_default} will be used.
        @param commands: A dict of commands for L{doCommand} to resolve.
        @type screen: C{gtk.gdk.Screen}
        @type commands: dict

        @todo: Confirm that the root window only changes on X11 server
               restart. (Something which will crash QuickTile anyway since
               PyGTK makes X server disconnects uncatchable.)

               It could possibly change while toggling "allow desktop icons"
               in KDE 3.x. (Not sure what would be equivalent elsewhere)
        """
        self._root = screen or gtk.gdk.screen_get_default()
        self.commands = commands
        self.ignore_workarea = ignore_workarea

    def cmd_cycleMonitors(self, window=None):
        """
        Cycle the specified window (the active window if none was explicitly
        specified) between monitors while leaving the position within the monitor
        unchanged.

        @returns: The target monitor ID or None if the current window could not
            be found.
        @rtype: C{int} or C{None}

        @bug: I may have to hack up my own maximization detector since
              win.get_state() seems to be broken.
        """

        win, _, winGeom, monitorID = self.getGeometries(window)

        if monitorID is None:
            return None

        if monitorID == 0:
            newMonitorID = 1
        else:
            newMonitorID = (monitorID + 1) % self._root.get_n_monitors()

        newMonitorGeom = self._root.get_monitor_geometry(newMonitorID)
        logging.debug("Moving window to monitor %s", newMonitorID)

        if win.get_state() & gtk.gdk.WINDOW_STATE_MAXIMIZED:
            self.cmd_toggleMaximize(win, False)
            self.reposition(win, winGeom, newMonitorGeom)
            self.cmd_toggleMaximize(win, True)
        else:
            self.reposition(win, winGeom, newMonitorGeom)

        return newMonitorID

    def cmd_toggleMaximize(self, win=None, state=None):
        """Given a window, toggle its maximization state or, optionally,
        set a specific state.

        @param win: The window on which to operate
        @param state: If this is not None, set a specific maximization state.
            Otherwise, toggle maximization.
        @type win: C{gtk.gdk.Window}
        @type state: C{bool} or C{None}

        @returns: The target state as a boolean (True = maximized) or None if
            the active window could not be retrieved.
        @rtype: C{bool} or C{None}

        @bug: win.unmaximize() seems to either have no effect or not get called
        """
        win = win or self.get_active_window()
        if not win:
            return None

        if state is False or (state is None and
                (win.get_state() & gtk.gdk.WINDOW_STATE_MAXIMIZED)):
            logging.debug('unmaximize')
            win.unmaximize()
            return False
        else:
            logging.debug('maximize')
            win.maximize()
            return True

    def cycleDimensions(self, dimensions, window=None):
        """
        Given a window and a list of 4-tuples containing dimensions as a decimal
        percentage of monitor size, cycle through the list, taking one step each
        time this function is called.

        If the window's dimensions are not in the list, set them to the first list
        entry.

        @returns: The new window dimensions.
        @rtype: C{gtk.gdk.Rectangle}
        """
        win, monitorGeom, winGeom = self.getGeometries(window)[0:3]

        # This temporary hack prevents an Exception with MPlayer.
        if not monitorGeom:
            return None

        # Resolve proportional (eg. 0.5) and preserved (None) coordinates
        dims = []
        for tup in dimensions:

            current_dim = []
            for pos, val in enumerate(tup):
                if val is None:
                    current_dim.append(tuple(winGeom)[pos])
                else:
                    # FIXME: This is a bit of an ugly way to get (w, h, w, h)
                    # from monitorGeom.
                    current_dim.append(int(val * tuple(monitorGeom)[2 + pos % 2]))

            dims.append(current_dim)

        if not dims:
            return None

        logging.debug("winGeom %r", tuple(winGeom))
        logging.debug("dims %r", dims)

        # Calculate euclidean distances between the window's current geometry
        # and all presets and store them in a min heap.
        euclid_distance = []
        for pos, val in enumerate(dims):
            distance = sum([(wg - vv) ** 2 for (wg, vv) in zip(tuple(winGeom), tuple(val))]) ** 0.5
            heappush(euclid_distance, (distance, pos))

        # If the window is already on one of the configured geometries, advance
        # to the next configuration. Otherwise, use the first configuration.
        min_distance = heappop(euclid_distance)
        if min_distance[0] < 100:
            pos = (min_distance[1] + 1) % len(dims)
        else:
            pos = 0
        result = gtk.gdk.Rectangle(*dims[pos])

        logging.debug("result %r", tuple(result))
        self.reposition(win, result, monitorGeom)
        return result

    def cmd_moveCenter(self, window=None):
        """
        Center the window in the current monitor.

        @returns: The new window dimensions.
        @rtype: C{gtk.gdk.Rectangle}
        """
        win, monitorGeom, winGeom = self.getGeometries(window)[0:3]

        logging.debug("win %r", win)
        logging.debug("monitorGeom %r", tuple(monitorGeom))
        logging.debug("winGeom %r", tuple(winGeom))

        # This temporary hack prevents an Exception with MPlayer.
        if not monitorGeom:
            return None

        dims = (int((monitorGeom.width - winGeom.width) / 2),
                 int((monitorGeom.height - winGeom.height) / 2),
                 int(winGeom.width),
                 int(winGeom.height))

        logging.debug("dims %r", dims)

        result = gtk.gdk.Rectangle(*dims)

        logging.debug("result %r", tuple(result))
        self.reposition(win, result, monitorGeom)
        return result


    def doCommand(self, command):
        """Resolve a textual positioning command and execute it.

        @returns: A boolean indicating success/failure.
        @type command: C{str}
        @rtype: C{bool}
        """
        int_command = self.commands.get(command, None)
        if isinstance(int_command, (tuple, list)):
            self.cycleDimensions(int_command)
            return True
        elif isinstance(int_command, basestring):
            cmd = getattr(self, 'cmd_' + int_command, None)
            if cmd:
                cmd()
                return True
            else:
                logging.error("Invalid internal command name: %s", int_command)
        elif int_command is None:
            logging.error("Invalid external command name: %r", command)
        else:
            logging.error("Unrecognized command type for %r", int_command)
        return False

    def get_active_window(self):
        """
        Retrieve the active window.

        @rtype: C{gtk.gdk.Screen} or C{None}
        @returns: The GDK Screen for the active window or None if the
            _NET_ACTIVE_WINDOW hint isn't supported or the desktop is the
            active window.

        @note: Checks for _NET* must be done every time since WMs support
               --replace
        """
        # Get the root and active window
        if (self._root.supports_net_wm_hint("_NET_ACTIVE_WINDOW") and
                self._root.supports_net_wm_hint("_NET_WM_WINDOW_TYPE")):
            win = self._root.get_active_window()
        else:
            return None

        # Observed breaking quicktile with git-gui on Metacity
        # TODO: Figure out how to prevent uncaught exceptions from making
        #       quicktile unresponsive in the general case.
        if win is None:
            return None

        # Do nothing if the desktop is the active window
        # (The "not winType" check seems required for fullscreen MPlayer)
        winType = win.property_get("_NET_WM_WINDOW_TYPE")
        logging.debug("NET_WM_WINDOW_TYPE: %r", winType)
        if winType and winType[-1][0] == '_NET_WM_WINDOW_TYPE_DESKTOP':
            return None

        return win

    def get_frame_thickness(self, win):
        """Given a window, return a (border, titlebar) thickness tuple.
        @type win: C{gtk.gdk.Window}

        @returns: A tuple of the form (window border thickness,
            titlebar thickness)
        @rtype: C{tuple(int, int)}
        """
        _or, _ror = win.get_origin(), win.get_root_origin()
        return _or[0] - _ror[0], _or[1] - _ror[1]

    def getGeometries(self, win=None):
        """
        Get the geometry for the given window (including window decorations)
        and the monitor it's on. If not window is specified, the active window
        is used.

        Returns a tuple of the window object, two gtk.gdk.Rectangle objects
        containing the monitor and window geometry, respectively, and the
        monitor ID (for multi-head desktops).

        Returns (None, None, None, None) if the specified window is a desktop
        window or if no window was specified and _NET_ACTIVE_WINDOW is unsupported.

        @type win: C{gtk.gdk.Window}
        @rtype: tuple

        @note: Window geometry is relative to the monitor, not the desktop.
        @note: Checks for _NET* must remain here here since WMs support --replace
        @todo: Confirm that changing WMs doesn't mess up quicktile.
        """
        # Get the active window
        win = win or self.get_active_window()
        if not win:
            return None, None, None, None

        #FIXME: How do I retrieve the root window from a given one?
        monitorID = self._root.get_monitor_at_window(win)
        monitorGeom = self._root.get_monitor_geometry(monitorID)

        #TODO: Support non-rectangular usable areas. (eg. Xinerama)
        # (And, once I've got a solution, mention it on http://stackoverflow.com/q/2598580/435253 )
        #
        # Potentially-useful stuff:
        # - http://old.nabble.com/Re%3A-_NET_WORKAREA-and-multiple-monitors-p24812662.html
        # - http://thread.gmane.org/gmane.comp.gnome.wm-spec/1531/focus=1772
        # - http://standards.freedesktop.org/wm-spec/wm-spec-1.3.html#id2507618
        if not self.ignore_workarea and self._root.supports_net_wm_hint("_NET_WORKAREA"):
            p = gtk.gdk.atom_intern('_NET_WORKAREA')
            desktopGeo = self._root.get_root_window().property_get(p)[2][0:4]
            monitorGeom = gtk.gdk.Rectangle(*desktopGeo).intersect(monitorGeom)

        # Get position relative to the monitor rather than the desktop
        winGeom = win.get_frame_extents()
        winGeom.x -= monitorGeom.x
        winGeom.y -= monitorGeom.y

        return win, monitorGeom, winGeom, monitorID

    def reposition(self, win, geom, monitor=gtk.gdk.Rectangle(0, 0, 0, 0)):
        """
        Position and size a window, decorations inclusive, according to the
        provided target window and monitor geometry rectangles.

        If no monitor rectangle is specified, position relative to the desktop
        as a whole.

        @type win: C{gtk.gdk.Window}
        @rtype: C{gtk.gdk.Rectangle}
        """
        #Workaround for my inability to reliably detect maximization.
        win.unmaximize()

        border, titlebar = self.get_frame_thickness(win)
        win.move_resize(geom.x + monitor.x, geom.y + monitor.y,
                geom.width - (border * 2), geom.height - (titlebar + border))

class QuickTileApp(object):
    keybinds_failed = False

    def __init__(self, wm, keys=None, modkeys=None):
        """@todo: document these arguments"""
        self.wm = wm
        self._keys = keys or {}
        self._modkeys = modkeys or 0

    def _init_dbus(self):
        """Setup dbus-python components in the PyGTK event loop"""
        class QuickTile(dbus.service.Object):
            def __init__(self):
                dbus.service.Object.__init__(self, sessBus, '/com/ssokolow/QuickTile')

            @dbus.service.method(dbus_interface='com.ssokolow.QuickTile',
                     in_signature='s', out_signature='b')
            def doCommand(self, command):
                return wm.doCommand(command)

        self.dbusName = dbus.service.BusName("com.ssokolow.QuickTile", sessBus)
        self.dbusObj = QuickTile()

    def _init_xlib(self):
        """Setup python-xlib components in the PyGTK event loop"""
        self.xdisp = Display()
        self.xroot = self.xdisp.screen().root

        # We want to receive KeyPress events
        self.xroot.change_attributes(event_mask=X.KeyPressMask)

        # unrecognized shortkeys now will be looked up in a hardcoded dict
        # and replaced by valid names like ',' -> 'comma'
        # while generating the self.keys dict
        self.keys = dict()
        for key in self._keys:
            transKey = key
            if key in KEYLOOKUP:
                transKey = KEYLOOKUP[key]
            self.keys[self.xdisp.keysym_to_keycode(string_to_keysym(transKey))] = self._keys[key]

        # Resolve strings to X11 mask constants for the modifier mask
        try:
            modmask = reduce(operator.ior, [getattr(X, "%sMask" % x) for x in self._modkeys])
        except Exception, err:
            logging.error("Error while resolving modifier key mask: %s", err)
            logging.error("Not binding keys for safety reasons. (eg. What if Ctrl+C got bound?)")
            modmask = 0
        else:
            self.xdisp.set_error_handler(self.handle_xerror)

            #XXX: Do I need to ignore Scroll lock too?
            for keycode in self.keys:
                #Ignore all combinations of Mod2 (NumLock) and Lock (CapsLock)
                for ignored in powerset([X.Mod2Mask, X.LockMask, X.Mod5Mask]):
                    ignored = reduce(lambda x, y: x | y, ignored, 0)
                    self.xroot.grab_key(keycode, modmask | ignored, 1, X.GrabModeAsync, X.GrabModeAsync)

        # If we don't do this, then nothing works.
        # I assume it flushes the XGrabKey calls to the server.
        self.xdisp.sync()
        if self.keybinds_failed:
            logging.warning("One or more requested keybindings were could not"
                " be bound. Please check that you are using valid X11 key"
                " names and that the keys are not already bound.")

        # Merge python-xlib into the Glib event loop
        gobject.io_add_watch(self.xroot.display, gobject.IO_IN, self.handle_xevent)

    def run(self):
        if XLIB_PRESENT:
            self._init_xlib()
        else:
            logging.error("Could not find python-xlib. Cannot bind keys.")

        if DBUS_PRESENT:
            self._init_dbus()
        else:
            logging.warn("Could not connect to the D-Bus Session Bus.")

        if not (XLIB_PRESENT or DBUS_PRESENT):
            raise DependencyError("Neither the Xlib nor the D-Bus backends were available.")

        gtk.main()

    def handle_xerror(self, err, req=None):
        """
        @note: If you can make python-xlib's C{CatchError} actually work or if
               you can retrieve more information to show, feel free.
        """
        if isinstance(err, BadAccess):
            self.keybinds_failed = True
        else:
            self.xdisp.display.default_error_handler(err)

    def handle_xevent(self, src, cond, handle=None):
        """Handle pending python-xlib events"""
        handle = handle or self.xroot.display

        for _ in range(0, handle.pending_events()):
            xevent = handle.next_event()
            if xevent.type == X.KeyPress:
                keycode = xevent.detail
                if keycode in self.keys:
                    self.wm.doCommand(self.keys[keycode])
                else:
                    logging.error("Received an event for an unrecognized keycode: %s" % keycode)
        return True

    def showBinds(self):
        maxlen_keys = max(len(x) for x in self._keys.keys())
        maxlen_vals = max(len(x) for x in self._keys.values())

        print "Keybindings defined for use with --daemonize:\n"

        print "Modifier: %s\n" % '+'.join(str(x) for x in self._modkeys)

        print "Key".ljust(maxlen_keys), "Action"
        print "-" * maxlen_keys, "-" * maxlen_vals
        for row in sorted(self._keys.items(), key=lambda x: x[0]):
            print row[0].ljust(maxlen_keys), row[1]

if __name__ == '__main__':
    from optparse import OptionParser, OptionGroup
    parser = OptionParser(usage="%prog [options] [action] ...",
            version="%%prog v%s" % __version__)
    parser.add_option('-d', '--daemonize', action="store_true", dest="daemonize",
        default=False, help="Attempt to set up global keybindings using "
        "python-xlib and a D-Bus service using dbus-python. Exit if neither "
        "succeeds")
    parser.add_option('-b', '--bindkeys', action="store_true", dest="daemonize",
        default=False, help="Deprecated alias for --daemonize")
    parser.add_option('--debug', action="store_true", dest="debug",
        default=False, help="Display debug messages")
    parser.add_option('--no-workarea', action="store_true", dest="no_workarea",
        default=False, help="Overlap panels but work better with "
        "non-rectangular desktops")

    help_group = OptionGroup(parser, "Additional Help")
    help_group.add_option('--show-bindings', action="store_true",
        dest="showBinds", default=False, help="List all configured keybindings")
    help_group.add_option('--show-actions', action="store_true", dest="showArgs",
        default=False, help="List valid arguments for use without --daemonize")
    parser.add_option_group(help_group)

    opts, args = parser.parse_args()

    if opts.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load the config from file if present
    # TODO: Refactor all this
    cfg_path = os.path.join(XDG_CONFIG_DIR, 'quicktile.cfg')
    config = RawConfigParser()
    config.optionxform = str # Make keys case-sensitive
    #TODO: Maybe switch to two config files so I can have only the keys in the keymap case-sensitive?
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

    modkeys = config.get('general', 'ModMask').split()

    # Either load the keybindings or use and save the defaults
    if config.has_section('keys'):
        keymap = dict(config.items('keys'))
    else:
        keymap = DEFAULTS['keys']
        config.add_section('keys')
        for row in keymap.items():
            config.set('keys', row[0], row[1])
        dirty = True

    if dirty:
        cfg_file = file(cfg_path, 'wb')
        config.write(cfg_file)
        cfg_file.close()

    ignore_workarea = (not config.getboolean('general', 'UseWorkarea')) or opts.no_workarea

    wm = WindowManager(POSITIONS, ignore_workarea=ignore_workarea)
    app = QuickTileApp(wm, keymap, modkeys=modkeys)

    if opts.showBinds:
        app.showBinds()
        sys.exit()

    if opts.daemonize:
        try:
            #TODO: Do this properly
            app.run()
        except DependencyError, err:
            logging.critical(err)
            sys.exit(errno.ENOENT)
            #FIXME: What's the proper exit code for "library not found"?

    elif not opts.daemonize:
        badArgs = [x for x in args if x not in wm.commands]
        if not args or badArgs or opts.showArgs:
            validArgs = sorted(wm.commands)

            if badArgs:
                print "Invalid argument(s): %s" % ' '.join(badArgs)

            print "Valid arguments are: \n\t%s" % '\n\t'.join(validArgs)

            if not opts.showArgs:
                print "\nUse --help for a list of valid options."
                sys.exit(errno.ENOENT)

        for arg in args:
            wm.doCommand(arg)
        while gtk.events_pending():
            gtk.main_iteration()
