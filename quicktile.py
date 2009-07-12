#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""QuickTile, a WinSplit clone for X11 desktops

Thanks to Thomas Vander Stichele for some of the documentation cleanups.

@bug: The internal keybindings only work with NumLock and CapsLock off.
@bug: The "monitor-switch" action only works on non-maximized windows.
@bug: The toggleMaximize function powering the "maximize" action can't unmaximize.
      (Workaround: Use one of the regular tiling actions to unmaximize)

@todo:
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
 - Expose a D-Bus API for --bindkeys and consider changing it so that, if
   python-xlib isn't present it displays an error message but keeps running
   anyway to provide the D-Bus service.
 - Can I hook into the GNOME and KDE keybinding APIs without using PyKDE or
   gnome-python? (eg. using D-Bus, perhaps?)

@todo: Merge remaining appropriate portions of:
 - https://thomas.apestaart.org/thomas/trac/changeset/1123/patches/quicktile/quicktile.py
 - https://thomas.apestaart.org/thomas/trac/changeset/1122/patches/quicktile/quicktile.py
 - https://thomas.apestaart.org/thomas/trac/browser/patches/quicktile/README

References and code used:
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

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

try:
    from Xlib import X
    from Xlib.display import Display
    from Xlib.keysymdef import miscellany as _m
    XLIB_PRESENT = True #: Indicates whether python-xlib was found
except ImportError:
    XLIB_PRESENT = False #: Indicates whether python-xlib was found

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

        @returns: The target monitor ID
        @rtype: int

        @bug: I may have to hack up my own maximization detector since
              win.get_state() seems to be broken.
        """

        win, monitorGeom, winGeom, monitorID = self.getGeometries(window)

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

        @returns: The target state as a boolean. (True = maximized)
        @rtype: bool

        @bug: win.unmaximize() seems to have no effect.
        """
        win = win or self.get_active_window()

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

        @bug: This currently trips over panels (eg. gnome-panel) unless they're
            hidden/auto-hide.
        """
        win, monitorGeom, winGeom = self.getGeometries(window)[0:3]

        dims = []
        for tup in dimensions:
            dims.append((int(tup[0] * monitorGeom.width),
                        int(tup[1] * monitorGeom.height),
                        int(tup[2] * monitorGeom.width),
                        int(tup[3] * monitorGeom.height)))

        result = gtk.gdk.Rectangle(*dims[0])
        for pos, val in enumerate(dims):
            if tuple(winGeom) == tuple(val):
                result = gtk.gdk.Rectangle(*dims[(pos + 1) % len(dims)])
                break

        self.reposition(win, result, monitorGeom)
        return result

    def doCommand(self, command):
        """Resolve a textual positioning command and execute it.

        @type command: C{str}
        """
        int_command = self.commands.get(command, None)
        if isinstance(int_command, (tuple, list)):
            self.cycleDimensions(int_command)
        elif isinstance(int_command, basestring):
            cmd = getattr(self, 'cmd_' + int_command, None)
            if cmd:
                cmd()
            else:
                logging.error("Invalid internal command name: %s", int_command)
        elif int_command is None:
            logging.error("Invalid external command name: %r", command)
        else:
            logging.error("Unrecognized command type for %r", int_command)

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
        if (win.property_get("_NET_WM_WINDOW_TYPE")[-1][0] ==
                '_NET_WM_WINDOW_TYPE_DESKTOP'):
            return None

        return win

    def get_combined_dimensions(self, win):
        """Given a window, return a tuple of:
        - the rectangle for its dimensions (frame included) relative to the
          monitor the window is on
        - the rectangle for the monitor the window is in relative to the root
          window

        @type win: C{gtk.gdk.Window}
        @rtype: C{gtk.gdk.Rectangle}
        """
        # Calculate the size of the wm decorations
        winw, winh = win.get_geometry()[2:4]
        border, titlebar = self.get_frame_thickness(win)
        w, h = winw + (border * 2), winh + (titlebar+border)

        # Calculate the position of where the wm decorations start (not the window itself)
        screenposx, screenposy = win.get_root_origin()

        # Adjust the position to make it relative to the monitor rather than
        # the desktop
        #FIXME: How do I retrieve the root window from a given one?
        monitorID = self._root.get_monitor_at_window(win)
        monitorGeom = self._root.get_monitor_geometry(monitorID)
        winGeom = gtk.gdk.Rectangle(screenposx - monitorGeom.x,
                screenposy - monitorGeom.y, w, h)

        return monitorGeom, winGeom

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
        win = self.get_active_window()
        if not win:
            return None, None, None, None

        # Calculate the size of the wm decorations
        winw, winh = win.get_geometry()[2:4]
        border, titlebar = self.get_frame_thickness(win)
        w, h = winw + (border * 2), winh + (titlebar+border)

        # Calculate the position of where the wm decorations start (not the window itself)
        screenposx, screenposy = win.get_root_origin()

        monitorID = self._root.get_monitor_at_window(win)
        monitorGeom = self._root.get_monitor_geometry(monitorID)
        winGeom = gtk.gdk.Rectangle(screenposx - monitorGeom.x,
                screenposy - monitorGeom.y, w, h)

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
        border, titlebar = self.get_frame_thickness(win)
        win.move_resize(geom.x + monitor.x, geom.y + monitor.y,
                geom.width - (border * 2), geom.height - (titlebar + border))

if __name__ == '__main__':
    from optparse import OptionParser
    parser = OptionParser(usage="%prog [options] [arguments]",
            version="%%prog v%s" % __version__)
    parser.add_option('-b', '--bindkeys', action="store_true", dest="daemonize",
        default=False, help="Use python-xlib to set up keybindings and then wait.")
    parser.add_option('--valid-args', action="store_true", dest="showArgs",
        default=False, help="List valid arguments for use without --bindkeys.")
    parser.add_option('--debug', action="store_true", dest="debug",
        default=False, help="List valid arguments for use without --bindkeys.")

    opts, args = parser.parse_args()

    if opts.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    wm = WindowManager(POSITIONS)
    if opts.daemonize:
        if not XLIB_PRESENT:
            print "ERROR: Could not find python-xlib. Cannot bind keys."
            sys.exit(errno.ENOENT)
            #FIXME: What's the proper exit code for "library not found"?

        disp = Display()
        root = disp.screen().root

        # We want to receive KeyPress events
        root.change_attributes(event_mask = X.KeyPressMask)
        keys = dict([(disp.keysym_to_keycode(x), keys[x]) for x in keys])

        for keycode in keys:
            root.grab_key(keycode, X.ControlMask | X.Mod1Mask, 1, X.GrabModeAsync, X.GrabModeAsync)

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
