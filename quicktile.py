#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""QuickTile, a WinSplit clone for X11 desktops

Thanks to Thomas Vander Stichele for some of the documentation cleanups.

@todo:
 - Reconsider use of C{--daemonize}. That tends to imply self-backgrounding.
 - Look into supporting XPyB (the Python equivalent to C{libxcb}) for global
   keybinding.
 - Clean up the code. It's functional, but an ugly rush-job.
 - Implement the secondary major features of WinSplit Revolution (eg.
   process-shape associations, locking/welding window edges, etc.)
 - Consider rewriting L{cycle_dimensions} to allow command-line use to jump to
   a specific index without actually flickering the window through all the
   intermediate shapes.
 - Can I hook into the GNOME and KDE keybinding APIs without using PyKDE or
   gnome-python? (eg. using D-Bus, perhaps?)

@todo: Merge remaining appropriate portions of:
 - U{https://thomas.apestaart.org/thomas/trac/changeset/1123/patches/quicktile/quicktile.py}
 - U{https://thomas.apestaart.org/thomas/trac/changeset/1122/patches/quicktile/quicktile.py}
 - U{https://thomas.apestaart.org/thomas/trac/browser/patches/quicktile/README}

@newfield appname: Application Name
"""

__appname__ = "QuickTile"
__author__  = "Stephan Sokolow (deitarion/SSokolow)"
__version__ = "0.2.0.1"
__license__ = "GNU GPL 2.0 or later"

import errno, operator, logging, os, sys
from ConfigParser import RawConfigParser
from heapq import heappop, heappush
from itertools import chain, combinations
from functools import wraps

import pygtk
pygtk.require('2.0')

import gtk, gobject, wnck

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
wnck.set_client_type(wnck.CLIENT_TYPE_PAGER)

try:
    from Xlib import X
    from Xlib.display import Display
    from Xlib.error import BadAccess
    from Xlib.XK import string_to_keysym
    XLIB_PRESENT = True  #: Indicates whether python-xlib was found
except ImportError:
    XLIB_PRESENT = False  #: Indicates whether python-xlib was found

DBUS_PRESENT = False  #: Indicates whether python-dbus was found
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
        sessBus = SessionBus()  #: Used by L{QuickTileApp._init_dbus}
    except DBusException:
        pass
    else:
        DBUS_PRESENT = True  #: Indicates whether python-dbus was found

XDG_CONFIG_DIR = os.environ.get('XDG_CONFIG_HOME',
                                os.path.expanduser('~/.config'))
#{ Settings

class GravityLayout(object):
    """Helper for generating L{cycle_dimensions} presets."""
    #TODO: Normalize these to the GTK or CSS terminology for 1.0
    GRAVITIES = {
        'top-left': (0.0, 0.0),
        'top': (0.5, 0.0),
        'top-right': (1.0, 0.0),
        'left': (0.0, 0.5),
        'middle': (0.5, 0.5),
        'right': (1.0, 0.5),
        'bottom-left': (0.0, 1.0),
        'bottom': (0.5, 1.0),
        'bottom-right': (1.0, 1.0),
    } #: Possible window alignments relative to the monitor/desktop.

    def __call__(self, w, h, gravity='top-left', x=None, y=None):
        """
        @param w: Desired width
        @param h: Desired height
        @param gravity: Desired window alignment from L{GRAVITIES}
        @param x: Desired horizontal position if not the same as C{gravity}
        @param y: Desired vertical position if not the same as C{gravity}

        @note: All parameters except C{gravity} are decimal values in the range
        C{0 <= x <= 1}.
        """

        x = x or self.GRAVITIES[gravity][0]
        y = y or self.GRAVITIES[gravity][1]
        offset_x = w * self.GRAVITIES[gravity][0]
        offset_y = h * self.GRAVITIES[gravity][1]

        return (x - offset_x,
                y - offset_y,
                w, h)

col, gv = 1.0 / 3, GravityLayout()

#TODO: Figure out how best to put this in the config file.
POSITIONS = {
    'middle': [gv(x, 1, 'middle') for x in (1.0, col, col * 2)],
}  #: command-to-position mappings for L{cycle_dimensions}

for grav in ('top', 'bottom'):
    POSITIONS[grav] = [gv(x, 0.5, grav) for x in (1.0, col, col * 2)]
for grav in ('left', 'right'):
    POSITIONS[grav] = [gv(x, 1, grav) for x in (0.5, col, col * 2)]
for grav in ('top-left', 'top-right', 'bottom-left', 'bottom-right'):
    POSITIONS[grav] = [gv(x, 0.5, grav) for x in (0.5, col, col * 2)]

#NOTE: For keysyms outside the latin1 and miscellany groups, you must first
#      call C{Xlib.XK.load_keysym_group()} with the name (minus extension) of
#      the appropriate module in site-packages/Xlib/keysymdef/*.py
#TODO: Migrate to gtk.accelerator_parse() and gtk.accelerator_valid()
#      Convert using '<%s>' % '><'.join(ModMask.split()))
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
}  #: Default content for the config file

KEYLOOKUP = {
    ',': 'comma',
    '.': 'period',
    '+': 'plus',
    '-': 'minus',
}  #: Used for resolving certain keysyms

#}
#{ Helpers

def powerset(iterable):
    "powerset([1,2,3]) --> () (1,) (2,) (3,) (1,2) (1,3) (2,3) (1,2,3)"
    s = list(iterable)
    return chain.from_iterable(combinations(s, r) for r in range(len(s) + 1))

#}
#{ Exceptions

class DependencyError(Exception):
    """Raised when a required dependency is missing."""
    pass

#}

class CommandRegistry(object):
    """Handles lookup and boilerplate for window management commands.

    Separated from WindowManager so its lifecycle is not tied to a specific
    GDK Screen object.
    """

    def __init__(self):
        self.commands = {}

    def __iter__(self):
        for x in self.commands:
            yield x

    def add(self, name, *p_args, **p_kwargs):
        """Decorator to wrap a function in boilerplate and add it to the
            command registry under the given name.

            @param name: The name to know the command by.
            @param p_args: Positional arguments to prepend to all calls made
                via C{name}.
            @param p_kwargs: Keyword arguments to prepend to all calls made
                via C{name}.

            @type name: C{str}
            """

        def decorate(func):
            @wraps(func)
            def wrapper(wm, window=None, *args, **kwargs):

                # Get Wnck and GDK window objects
                window = window or wm.screen.get_active_window()
                if isinstance(window, gtk.gdk.Window):
                    win = wnck.window_get(window.xid)
                else:
                    win = window

                logging.debug("window: %s", win)
                if not win:
                    return None

                monitor_id, monitor_geom = wm.get_monitor(window)

                use_area, use_rect = wm.get_workarea(monitor_geom,
                                                     wm.ignore_workarea)

                # TODO: Replace this MPlayer safety hack with a properly
                #       comprehensive exception catcher.
                if not use_rect:
                    logging.debug("use_rect: %s", use_rect)
                    return None

                state = {
                    "cmd_name": name,
                    "monitor_id": monitor_id,
                    "monitor_geom": monitor_geom,
                    "usable_region": use_area,
                    "usable_rect": use_rect,
                }

                args, kwargs = p_args + args, dict(p_kwargs, **kwargs)
                func(wm, win, state, *args, **kwargs)

            if name in self.commands:
                logging.warn("Overwriting command: %s", name)
            self.commands[name] = wrapper

            # Return the unwrapped function so decorators can be stacked
            # to define multiple commands using the same code with different
            # arguments
            return func
        return decorate

    def addMany(self, command_map):
        """Convenience decorator to allow many commands to be defined from
           the same function with different arguments.

           @param command_map: A dict mapping command names to argument lists.
           @type command_map: C{dict}
        """
        def decorate(func):
            for cmd, arglist in command_map.items():
                self.add(cmd, *arglist)(func)
            return func
        return decorate

    def call(self, command, wm, *args, **kwargs):
        """Resolve a textual positioning command and execute it."""
        cmd = self.commands.get(command, None)

        if cmd:
            cmd(wm, *args, **kwargs)
        else:
            logging.error("Unrecognized command: %s", command)

class WindowManager(object):
    """A simple API-wrapper class for manipulating window positioning."""
    def __init__(self, screen=None, ignore_workarea=False):
        """
        Initializes C{WindowManager}.

        @param screen: The X11 screen to operate on. If C{None}, the default
            screen as retrieved by C{gtk.gdk.screen_get_default} will be used.
        @type screen: C{gtk.gdk.Screen}

        @todo: Confirm that the root window only changes on X11 server
               restart. (Something which will crash QuickTile anyway since
               PyGTK makes X server disconnects uncatchable.)

               It could possibly change while toggling "allow desktop icons"
               in KDE 3.x. (Not sure what would be equivalent elsewhere)
        """
        self.gdk_screen = screen or gtk.gdk.screen_get_default()
        self.screen = wnck.screen_get(self.gdk_screen.get_number())
        self.ignore_workarea = ignore_workarea

    def get_geometry_rel(self, window, monitor_geom):
        """Get window position relative to the monitor rather than the desktop.

        @param monitor_geom: The rectangle returned by
            C{gdk.Screen.get_monitor_geometry}
        @type window: C{wnck.Window}
        @type monitor_geom: C{gtk.gdk.Rectangle}

        @rtype: C{gtk.gdk.Rectangle}
        """
        win_geom = gtk.gdk.Rectangle(*window.get_geometry())
        win_geom.x -= monitor_geom.x
        win_geom.y -= monitor_geom.y

        return win_geom

    def get_monitor(self, win):
        """Given a Window (Wnck or GDK), retrieve the monitor ID and geometry.

        @type win: C{wnck.Window} or C{gtk.gdk.Window}
        @returns: A tuple containing the monitor ID and geometry.
        @rtype: C{(int, gtk.gdk.Rectangle)}
        """
        #TODO: Look for a way to get the monitor ID without having
        #      to instantiate a gtk.gdk.Window
        if not isinstance(win, gtk.gdk.Window):
            win = gtk.gdk.window_foreign_new(win.get_xid())

        #TODO: How do I retrieve the root window from a given one?
        monitor_id = wm.gdk_screen.get_monitor_at_window(win)
        monitor_geom = wm.gdk_screen.get_monitor_geometry(monitor_id)

        logging.debug("Monitor: %s, %s", monitor_id, monitor_geom)
        return monitor_id, monitor_geom

    def get_workarea(self, monitor, ignore_struts=False):
        """Retrieve the usable area of the specified monitor using
        the most expressive method the window manager supports.

        @param monitor: The number or dimensions of the desired monitor.
        @param ignore_struts: If C{True}, just return the size of the whole
            monitor, allowing windows to overlap panels.
        @type monitor: C{int} or C{gtk.gdk.Rectangle}
        @type ignore_struts: C{bool}

        @returns: The usable region and its largest rectangular subset.
        @rtype: C{gtk.gdk.Region}, C{gtk.gdk.Rectangle}
        """
        if isinstance(monitor, int):
            usableRect = self.gdk_screen.get_monitor_geometry(monitor)
        elif not isinstance(monitor, gtk.gdk.Rectangle):
            usableRect = gtk.gdk.Rectangle(monitor)
        else:
            usableRect = monitor
        usableRegion = gtk.gdk.region_rectangle(usableRect)

        if ignore_struts:
            return usableRegion, usableRect

        rootWin = self.gdk_screen.get_root_window()

        # TODO: Test and extend to support panels on asymmetric monitors
        struts = []
        if self.gdk_screen.supports_net_wm_hint("_NET_WM_STRUT_PARTIAL"):
            # Gather all struts
            struts.append(rootWin.property_get("_NET_WM_STRUT_PARTIAL"))
            if (self.gdk_screen.supports_net_wm_hint("_NET_CLIENT_LIST")):
                # Source: http://stackoverflow.com/a/11332614/435253
                for id in rootWin.property_get('_NET_CLIENT_LIST')[2]:
                    w = gtk.gdk.window_foreign_new(id)
                    struts.append(w.property_get("_NET_WM_STRUT_PARTIAL"))
            struts = [x[2] for x in struts if x]

            # Subtract the struts from the usable region
            _Su = lambda *g: usableRegion.subtract(gtk.gdk.region_rectangle(g))
            _w, _h = self.gdk_screen.get_width(), self.gdk_screen.get_height()
            for g in struts:
                # http://standards.freedesktop.org/wm-spec/1.5/ar01s05.html
                # XXX: Must not cache unless watching for notify events.
                _Su(0, g[4], g[0], g[5] - g[4] + 1)             # left
                _Su(_w - g[1], g[6], g[1], g[7] - g[6] + 1)     # right
                _Su(g[8], 0, g[9] - g[8] + 1, g[2])             # top
                _Su(g[10], _h - g[3], g[11] - g[10] + 1, g[3])  # bottom

            # Generate a more restrictive version used as a fallback
            usableRect = usableRegion.copy()
            _Su = lambda *g: usableRect.subtract(gtk.gdk.region_rectangle(g))
            for g in struts:
                # http://standards.freedesktop.org/wm-spec/1.5/ar01s05.html
                # XXX: Must not cache unless watching for notify events.
                _Su(0, g[4], g[0], _h)          # left
                _Su(_w - g[1], g[6], g[1], _h)  # right
                _Su(0, 0, _w, g[2])             # top
                _Su(0, _h - g[3], _w, g[3])     # bottom
                # TODO: The required "+ 1" in certain spots confirms that we're
                #       going to need unit tests which actually check that the
                #       WM's code for constraining windows to the usable area
                #       doesn't cause off-by-one bugs.
                #TODO: Share this on http://stackoverflow.com/q/2598580/435253
            usableRect = usableRect.get_clipbox()
        elif self.gdk_screen.supports_net_wm_hint("_NET_WORKAREA"):
            desktopGeo = tuple(rootWin.property_get('_NET_WORKAREA')[2][0:4])
            usableRegion.intersect(gtk.gdk.region_rectangle(desktopGeo))
            usableRect = usableRegion.get_clipbox()

        return usableRegion, usableRect

    def reposition(self, win, geom=None, monitor=gtk.gdk.Rectangle(0, 0, 0, 0),
            keep_maximize=False):
        """
        Position and size a window, decorations inclusive, according to the
        provided target window and monitor geometry rectangles.

        If no monitor rectangle is specified, position relative to the desktop
        as a whole.

        @param monitor: The frame relative to which C{geom} should be
            interpreted. Leave at the default for the whole desktop.
        @param keep_maximize: Whether to re-maximize a maximized window after
            un-maximizing it to move it.
        @type win: C{gtk.gdk.Window}
        @type geom: C{gtk.gdk.Rectangle}
        @type monitor: C{gtk.gdk.Rectangle}
        @type keep_maximize: C{bool}
        """

        geom = geom or wm.get_geometry_rel(win, wm.get_monitor(win)[1])

        max_types, maxed = ['', '_horizontally', '_vertically'], []
        for mt in max_types:
            if getattr(win, 'is_maximized' + mt)():
                maxed.append(mt)
                getattr(win, 'unmaximize' + mt)()

        new_x, new_y = geom.x + monitor.x, geom.y + monitor.y
        logging.debug("repositioning to (%d, %d, %d, %d)",
                new_x, new_y, geom.width, geom.height)

        #XXX: Why is WINDOW_GRAVITY_STATIC behaving as the libwnck docs say
        #       that WINDOW_GRAVITY_NORTHWEST should?
        win.set_geometry(wnck.WINDOW_GRAVITY_STATIC,
                wnck.WINDOW_CHANGE_X | wnck.WINDOW_CHANGE_Y |
                wnck.WINDOW_CHANGE_WIDTH | wnck.WINDOW_CHANGE_HEIGHT,
                new_x, new_y, geom.width, geom.height)

        if maxed and keep_maximize:
            for mt in maxed:
                getattr(win, 'maximize' + mt)()

class QuickTileApp(object):
    """The basic Glib application itself."""
    keybinds_failed = False

    def __init__(self, wm, commands, keys=None, modkeys=None):
        """Populate the instance variables.

        @param keys: A dict mapping X11 keysyms to L{CommandRegistry}
            command names.
        @param modkeys: A modifier mask to prefix to all keybindings.
        @type wm: The L{WindowManager} instance to use.
        @type keys: C{dict}
        @type modkeys: C{str}
        """
        self.wm = wm
        self.commands = commands
        self._keys = keys or {}
        self._modkeys = modkeys or 0

    def _init_dbus(self):
        """Set up dbus-python components in the Glib event loop

        @todo 1.0.0: Retire the C{doCommand} name. (API-breaking)
        """
        class QuickTile(dbus.service.Object):
            def __init__(self):
                dbus.service.Object.__init__(self, sessBus,
                                             '/com/ssokolow/QuickTile')

            @dbus.service.method(dbus_interface='com.ssokolow.QuickTile',
                     in_signature='s', out_signature='b')
            def doCommand(self, command):
                return self.commands.call(command, wm)

        self.dbusName = dbus.service.BusName("com.ssokolow.QuickTile", sessBus)
        self.dbusObj = QuickTile()

    def _init_xlib(self):
        """Set up python-xlib components in the Glib event loop

        Source: U{http://www.larsen-b.com/Article/184.html}
        """
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
            code = self.xdisp.keysym_to_keycode(string_to_keysym(transKey))
            self.keys[code] = self._keys[key]

        # Resolve strings to X11 mask constants for the modifier mask
        try:
            modmask = reduce(operator.ior, [getattr(X, "%sMask" % x)
                             for x in self._modkeys])
        except Exception, err:
            logging.error("Error while resolving modifier key mask: %s", err)
            logging.error("Not binding keys for safety reasons. "
                          "(eg. What if Ctrl+C got bound?)")
            modmask = 0
        else:
            self.xdisp.set_error_handler(self.handle_xerror)

            #XXX: Do I need to ignore Scroll lock too?
            for keycode in self.keys:
                #Ignore all combinations of Mod2 (NumLock) and Lock (CapsLock)
                for ignored in powerset([X.Mod2Mask, X.LockMask, X.Mod5Mask]):
                    ignored = reduce(lambda x, y: x | y, ignored, 0)
                    self.xroot.grab_key(keycode, modmask | ignored, 1,
                                        X.GrabModeAsync, X.GrabModeAsync)

        # If we don't do this, then nothing works.
        # I assume it flushes the XGrabKey calls to the server.
        self.xdisp.sync()
        if self.keybinds_failed:
            logging.warning("One or more requested keybindings were could not"
                " be bound. Please check that you are using valid X11 key"
                " names and that the keys are not already bound.")

        # Merge python-xlib into the Glib event loop
        # Source: http://www.pygtk.org/pygtk2tutorial/sec-MonitoringIO.html
        gobject.io_add_watch(self.xroot.display,
                             gobject.IO_IN, self.handle_xevent)

    def run(self):
        """Call L{_init_xlib} and L{_init_dbus} if available, then
        call C{gtk.main()}."""

        if XLIB_PRESENT:
            self._init_xlib()
        else:
            logging.error("Could not find python-xlib. Cannot bind keys.")

        if DBUS_PRESENT:
            self._init_dbus()
        else:
            logging.warn("Could not connect to the D-Bus Session Bus.")

        if not (XLIB_PRESENT or DBUS_PRESENT):
            raise DependencyError("Neither the Xlib nor the D-Bus backends "
                                  "were available.")

        gtk.main()

    def handle_xerror(self, err, req=None):
        """Used to identify when attempts to bind keys fail.
        @note: If you can make python-xlib's C{CatchError} actually work or if
               you can retrieve more information to show, feel free.
        """
        if isinstance(err, BadAccess):
            self.keybinds_failed = True
        else:
            self.xdisp.display.default_error_handler(err)

    def handle_xevent(self, src, cond, handle=None):
        """Handle pending python-xlib events.

        Filters for C{X.KeyPress} events, resolves them to commands, and calls
        L{CommandRegistry.call} on them.
        """
        handle = handle or self.xroot.display

        for _ in range(0, handle.pending_events()):
            xevent = handle.next_event()
            if xevent.type == X.KeyPress:
                keycode = xevent.detail
                if keycode in self.keys:
                    self.commands.call(self.keys[keycode], wm)
                else:
                    logging.error("Received an event for an unrecognized "
                                  "keycode: %s" % keycode)
        return True

    def showBinds(self):
        """Print a formatted readout of defined keybindings and the modifier
        mask to stdout."""

        maxlen_keys = max(len(x) for x in self._keys.keys())
        maxlen_vals = max(len(x) for x in self._keys.values())

        print "Keybindings defined for use with --daemonize:\n"

        print "Modifier: %s\n" % '+'.join(str(x) for x in self._modkeys)

        print "Key".ljust(maxlen_keys), "Action"
        print "-" * maxlen_keys, "-" * maxlen_vals
        for row in sorted(self._keys.items(), key=lambda x: x[0]):
            print row[0].ljust(maxlen_keys), row[1]

commands = CommandRegistry()
#{ Tiling Commands

@commands.addMany(POSITIONS)
def cycle_dimensions(wm, win, state, *dimensions):
    """
    Given a list of shapes and a window, cycle through the list, taking one
    step each time this function is called.

    If the window's dimensions are not within 100px (by euclidean distance)
    of an entry in the list, set them to the first list entry.

    @param dimensions: A list of tuples representing window geometries as
        floating-point values between 0 and 1, inclusive.
    @type dimensions: C{[(x, y, w, h), ...]}
    @type win: C{gtk.gdk.Window}

    @returns: The new window dimensions.
    @rtype: C{gtk.gdk.Rectangle}
    """
    win_geom = wm.get_geometry_rel(win, state['monitor_geom'])
    usable_region = state['usable_region']

    # Get the bounding box for the usable region (overlaps panels which
    # don't fill 100% of their edge of the screen)
    clipBox = usable_region.get_clipbox()

    # Resolve proportional (eg. 0.5) and preserved (None) coordinates
    dims = []
    for tup in dimensions:
        current_dim = []
        for pos, val in enumerate(tup):
            if val is None:
                current_dim.append(tuple(win_geom)[pos])
            else:
                # FIXME: This is a bit of an ugly way to get (w, h, w, h)
                # from clipBox.
                current_dim.append(int(val * tuple(clipBox)[2 + pos % 2]))

        dims.append(current_dim)

    if not dims:
        return None

    logging.debug("dims %r", dims)

    # Calculate euclidean distances between the window's current geometry
    # and all presets and store them in a min heap.
    euclid_distance = []
    for pos, val in enumerate(dims):
        distance = sum([(wg - vv) ** 2 for (wg, vv)
                        in zip(tuple(win_geom), tuple(val))]) ** 0.5
        heappush(euclid_distance, (distance, pos))

    # If the window is already on one of the configured geometries, advance
    # to the next configuration. Otherwise, use the first configuration.
    min_distance = heappop(euclid_distance)
    if min_distance[0] < 100:
        pos = (min_distance[1] + 1) % len(dims)
    else:
        pos = 0
    result = gtk.gdk.Rectangle(*dims[pos])
    result.x += clipBox.x
    result.y += clipBox.y

    # If we're overlapping a panel, fall back to a monitor-specific
    # analogue to _NET_WORKAREA to prevent overlapping any panels and
    # risking the WM potentially meddling with the result of resposition()
    if not usable_region.rect_in(result) == gtk.gdk.OVERLAP_RECTANGLE_IN:
        logging.debug("Result overlaps panel. Falling back to usableRect.")
        result = result.intersect(state['usable_rect'])

    logging.debug("result %r", tuple(result))
    wm.reposition(win, result)
    return result

@commands.add('monitor-switch')
def cycle_monitors(wm, win, state):
    """
    Cycle the specified window (the active window if C{window=None}
    between monitors while leaving the position within the monitor
    unchanged.
    """
    mon_id = state['monitor_id']

    if mon_id == 0:
        new_mon_id = 1
    else:
        new_mon_id = (mon_id + 1) % wm.gdk_screen.get_n_monitors()

    new_mon_geom = wm.gdk_screen.get_monitor_geometry(new_mon_id)
    logging.debug("Moving window to monitor %s", new_mon_id)

    wm.reposition(win, None, new_mon_geom, keep_maximize=True)

@commands.add('move-to-center')
def cmd_moveCenter(wm, win, state):
    """Center the window in the monitor it currently occupies."""
    use_rect = state['usable_rect']
    win_geom = wm.get_geometry_rel(win, state['monitor_geom'])

    #FIXME: Just use use_rect/2 and libwnck's gravity support.
    dims = (int((use_rect.width - win_geom.width) / 2),
            int((use_rect.height - win_geom.height) / 2),
            int(win_geom.width),
            int(win_geom.height))

    logging.debug("dims %r", dims)
    result = gtk.gdk.Rectangle(*dims)
    logging.debug("result %r", tuple(result))

    wm.reposition(win, result, use_rect)

@commands.add('maximize', 'maximize')
@commands.add('vertical-maximize', 'maximize_vertically')
@commands.add('horizontal-maximize', 'maximize_horizontally')
def toggle_state(wm, win, state, command):
    """Given a window, toggle a state attribute like maximization.

    @param command: The C{wnck.Window} method name to be conditionally prefixed
        with "un", resolved, and called.
    @type command: C{str}
    """
    target = not win.is_maximized()

    logging.debug('maximize: %s', target)
    getattr(win, ('' if target else 'un') + command)()

#}

if __name__ == '__main__':
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
        dest="showBinds", default=False, help="List all configured keybinds")
    help_group.add_option('--show-actions', action="store_true",
        dest="showArgs", default=False, help="List valid arguments for use "
        "without --daemonize")
    parser.add_option_group(help_group)

    opts, args = parser.parse_args()

    if opts.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load the config from file if present
    # TODO: Refactor all this
    cfg_path = os.path.join(XDG_CONFIG_DIR, 'quicktile.cfg')
    first_run = not os.path.exists(cfg_path)

    config = RawConfigParser()
    config.optionxform = str  # Make keys case-sensitive
    #TODO: Maybe switch to two config files so I can have only the keys in the
    #      keymap case-sensitive?
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
        if first_run:
            logging.info("Wrote default config file to %s", cfg_path)

    ignore_workarea = ((not config.getboolean('general', 'UseWorkarea'))
                       or opts.no_workarea)

    wm = WindowManager(ignore_workarea=ignore_workarea)
    app = QuickTileApp(wm, commands, keymap, modkeys=modkeys)

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
    elif not first_run:
        badArgs = [x for x in args if x not in commands]
        if not args or badArgs or opts.showArgs:
            validArgs = sorted(commands)

            if badArgs:
                print "Invalid argument(s): %s" % ' '.join(badArgs)

            print "Valid arguments are: \n\t%s" % '\n\t'.join(validArgs)

            if not opts.showArgs:
                print "\nUse --help for a list of valid options."
                sys.exit(errno.ENOENT)
        else:
            #TODO: Fix this properly so I doesn't need to call a private member
            wm.screen.force_update()

            for arg in args:
                commands.call(arg, wm)
            while gtk.events_pending():
                gtk.main_iteration()
