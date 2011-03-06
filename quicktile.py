#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""QuickTile, a WinSplit clone for X11 desktops

Thanks to Thomas Vander Stichele for some of the documentation cleanups.

@bug: The toggleMaximize function powering the "maximize" action can't unmaximize.
      (Workaround: Use one of the regular tiling actions to unmaximize)

@todo:
 - Look into supporting xpyb (the Python equivalent to libxcb) for global
   keybinding.
 - Decide whether to amend the euclidean distance matching so un-tiled windows
   are guaranteed to start at the beginning of the sequence.
 - Clean up the code. It's functional, but an ugly rush-job.
 - Figure out how to implement a --list-keybindings option.
 - Decide how to handle maximization and stick with it.
 - Implement the secondary major features of WinSplit Revolution (eg.
   process-shape associations, locking/welding window edges, etc.)
 - Consider binding KP+ and KP- to allow comfy customization of split widths.
   (or heights, for the vertical split)
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
__version__ = "0.1.4"
__license__ = "GNU GPL 2.0 or later"


import pygtk
pygtk.require('2.0')

import errno, logging, gtk, gobject, sys
from heapq import heappop, heappush

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

try:
    from Xlib import X
    from Xlib.display import Display
    from Xlib.keysymdef import miscellany as _m
    XLIB_PRESENT = True #: Indicates whether python-xlib was found
except ImportError:
    XLIB_PRESENT = False #: Indicates whether python-xlib was found

try:
    import dbus.service
    from dbus import SessionBus
    from dbus.mainloop.glib import DBusGMainLoop

    DBusGMainLoop(set_as_default=True)
    sessBus = SessionBus()
    DBUS_PRESENT = True
except: # TODO: figure out what signal other than ImportError to catch
    DBUS_PRESENT = False

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
    'maximize'       : 'toggleMaximize',
    'monitor-switch' : 'cycleMonitors',
} #: command-to-action mappings

if XLIB_PRESENT:
    keys = {
        _m.XK_KP_0     : "maximize",
        _m.XK_KP_1     : "bottom-left",
        _m.XK_KP_2     : "bottom",
        _m.XK_KP_3     : "bottom-right",
        _m.XK_KP_4     : "left",
        _m.XK_KP_5     : "middle",
        _m.XK_KP_6     : "right",
        _m.XK_KP_7     : "top-left",
        _m.XK_KP_8     : "top",
        _m.XK_KP_9     : "top-right",
        _m.XK_KP_Enter : "monitor-switch",
    } #: keybinding-to-command mappings

class WindowManager(object):
    """A simple API-wrapper class for manipulating window positioning."""
    def __init__(self, commands, screen=None):
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

        win, monitorGeom, winGeom, monitorID = self.getGeometries(window)

        if monitorID is None:
            return None

        if monitorID == 0:
            newMonitorID = 1
        else:
            newMonitorID = (monitorID + 1) % self._root.get_n_monitors()

        newMonitorGeom = self._root.get_monitor_geometry(newMonitorID)
        logging.debug("Moving window to monitor %s" % newMonitorID)

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

        dims = []
        for tup in dimensions:
            dims.append((int(tup[0] * monitorGeom.width),
                        int(tup[1] * monitorGeom.height),
                        int(tup[2] * monitorGeom.width),
                        int(tup[3] * monitorGeom.height)))

        logging.debug("winGeom %r", tuple(winGeom))
        logging.debug("dims %r", dims)

        # Calculate euclidean distances between the window's current geometry
        # and all presets and store them in a min heap.
        euclid_distance = []
        for pos, val in enumerate(dims):
            distance = sum([(wg-vv)**2 for (wg, vv) in zip(tuple(winGeom), tuple(val))])
            heappush(euclid_distance, (distance, pos))

        # Get minimum euclidean distance. (Closest match)
        pos = heappop(euclid_distance)[1]
        result = gtk.gdk.Rectangle(*dims[(pos + 1) % len(dims)])

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

        # Do nothing if the desktop is the active window
        # (The "not winType" check seems required for fullscreen MPlayer)
        winType = win.property_get("_NET_WM_WINDOW_TYPE")
        logging.debug("NET_WM_WINDOW_TYPE: %r", winType)
        if not winType or winType[-1][0] == '_NET_WM_WINDOW_TYPE_DESKTOP':
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
        if self._root.supports_net_wm_hint("_NET_WORKAREA"):
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

if __name__ == '__main__':
    from optparse import OptionParser
    parser = OptionParser(usage="%prog [options] [arguments]",
            version="%%prog v%s" % __version__)
    parser.add_option('-d', '--daemonize', action="store_true", dest="daemonize",
        default=False, help="Attempt to set up global keybindings using "
        "python-xlib and a D-Bus service using dbus-python. Exit if neither "
        "succeeds.")
    parser.add_option('-b', '--bindkeys', action="store_true", dest="daemonize",
        default=False, help="Deprecated alias for --daemonize.")
    parser.add_option('--valid-args', action="store_true", dest="showArgs",
        default=False, help="List valid arguments for use without --bindkeys.")
    parser.add_option('--debug', action="store_true", dest="debug",
        default=False, help="Display debug messages.")

    opts, args = parser.parse_args()

    if opts.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    wm = WindowManager(POSITIONS)
    if opts.daemonize:
        success = False     # This will be changed on success

        if XLIB_PRESENT:
            disp = Display()
            root = disp.screen().root

            # We want to receive KeyPress events
            root.change_attributes(event_mask = X.KeyPressMask)
            keys = dict([(disp.keysym_to_keycode(x), keys[x]) for x in keys])

            for keycode in keys:
                root.grab_key(keycode, X.ControlMask | X.Mod1Mask, 1, X.GrabModeAsync, X.GrabModeAsync)
                root.grab_key(keycode, X.ControlMask | X.Mod1Mask | X.Mod2Mask, 1, X.GrabModeAsync, X.GrabModeAsync)
                root.grab_key(keycode, X.ControlMask | X.Mod1Mask | X.Mod2Mask | X.LockMask, 1, X.GrabModeAsync, X.GrabModeAsync)
                root.grab_key(keycode, X.ControlMask | X.Mod1Mask | X.LockMask, 1, X.GrabModeAsync, X.GrabModeAsync)

            # If we don't do this, then nothing works.
            # I assume it flushes the XGrabKey calls to the server.
            for x in range(0, root.display.pending_events()):
                root.display.next_event()

            def handle_xevent(src, cond, handle=root.display):
                """Handle pending python-xlib events"""
                for i in range(0, handle.pending_events()):
                    xevent = handle.next_event()
                    if xevent.type == X.KeyPress:
                        keycode = xevent.detail
                        wm.doCommand(keys[keycode])
                return True

            # Merge python-xlib into the Glib event loop and start things going.
            gobject.io_add_watch(root.display, gobject.IO_IN, handle_xevent)
            success = True
        else:
            logging.error("Could not find python-xlib. Cannot bind keys.")

        if DBUS_PRESENT:
            class QuickTile(dbus.service.Object):
                def __init__(self):
                    dbus.service.Object.__init__(self, sessBus, '/com/ssokolow/QuickTile')

                @dbus.service.method(dbus_interface='com.ssokolow.QuickTile',
                         in_signature='s', out_signature='b')
                def doCommand(self, command):
                    return wm.doCommand(command)

            dbusName = dbus.service.BusName("com.ssokolow.QuickTile", sessBus)
            dbusObj = QuickTile()
            success = True
        else:
            logging.warn("Could not connect to the D-Bus Session Bus.")

        if not success:
            sys.exit(errno.ENOENT)
            #FIXME: What's the proper exit code for "library not found"?

        gtk.main()
    elif not opts.daemonize:
        badArgs = [x for x in args if x not in wm.commands]
        if not args or badArgs or opts.showArgs:
            # sorted() was added in 2.4 and everything else should be 2.3-safe.
            validArgs = list(wm.commands)
            validArgs.sort()

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
