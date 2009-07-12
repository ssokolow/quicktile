#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""deitarion/SSokolow's Linux WinSplit clone in need of a name

When using --bindkeys, keybindings are Ctrl+Alt+0 through Ctrl+Alt+9 and
Ctrl+Alt+Enter (keypad only). For non-keybinding use, see --help.

Requirements:
- Python 2.3 (Tested on 2.5 but I don't see any newer constructs in the code.)
- PyGTK 2.2 (assuming get_active_window() isn't newer than that)
- X11 (The code expects _NETWM hints and X11-style window decorations)
- python-xlib (optional, required for --bindkeys, tested with 0.12)

Known Bugs:
- The internal keybindings only work with NumLock and CapsLock off.
- The "monitor-switch" action only works on non-maximized windows.
- The toggleMaximize function powering the "maximize" action can't unmaximize.
  (Workaround: Use one of the regular tiling actions to unmaximize)

TODO:
- Decide how to handle maximization and stick with it.
- Implement the secondary major features of WinSplit Revolution (eg.
  process-shape associations, locking/welding window edges, etc.)
- Clean up the code. It's functional, but an ugly rush-job.
- Figure out how to implement a --list-keybindings option.
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

References and code used:
- http://faq.pygtk.org/index.py?req=show&file=faq23.039.htp
- http://www.larsen-b.com/Article/184.html
- http://www.pygtk.org/pygtk2tutorial/sec-MonitoringIO.html
"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__version__ = "0.1.3"
__license__ = "GNU GPL 2.0 or later"


import pygtk
pygtk.require('2.0')

import errno, gtk, gobject, sys

try:
    from Xlib import X
    from Xlib.display import Display
    from Xlib.keysymdef import miscellany as _m
    XLIB_PRESENT = True
except ImportError:
    XLIB_PRESENT = False

def cycleMonitors(window=None):
    """
    Cycle the specified window (the active window if none was explicitly
    specified) between monitors while leaving the position within the monitor
    unchanged.
    """

    win, monitorG, winG, monitorID = getGeometries()

    root = gtk.gdk.screen_get_default()
    monitorCount = root.get_n_monitors()

    newMonitorID = (monitorID + 1 < monitorCount) and monitorID + 1 or 0
    newMonitorG = root.get_monitor_geometry(newMonitorID)

    if win.get_state() & gtk.gdk.WINDOW_STATE_MAXIMIZED:
        toggleMaximize(win)
        positionWindow(win, winG, newMonitorG)
        toggleMaximize(win)
    else:
        positionWindow(win, winG, newMonitorG)

def toggleMaximize(win=None, state=None):
    if not win:
        win, monitorG, winG, monitorID = getGeometries()

    if state is False or (state is None and (win.get_state() & gtk.gdk.WINDOW_STATE_MAXIMIZED)):
        win.unmaximize() #FIXME: This isn't doing anything for some reason.
    else:
        win.maximize()

positions = {
    'left'           : ((0,     0,   0.5,   1  ), (0,         0,   1.0/3, 1  ), (0,     0,   1.0/3 * 2, 1)),
    'middle'         : ((0,     0,     1,   1  ), (1.0/3,     0,   1.0/3, 1  ), (1.0/6, 0,   1.0/3 * 2, 1)),
    'right'          : ((0.5,   0,   0.5,   1  ), (1.0/3 * 2, 0,   1.0/3, 1  ), (1.0/3, 0,   1.0/3 * 2, 1)),
    'top'            : ((0,     0,   1,     0.5), (1.0/3,     0,   1.0/3, 0.5)),
    'bottom'         : ((0,     0.5, 1,     0.5), (1.0/3,     0.5, 1.0/3, 0.5)),
    'top-left'       : ((0,     0,   0.5,   0.5), (0,         0,   1.0/3, 0.5), (0,     0,   1.0/3 * 2, 0.5)),
    'top-right'      : ((0.5,   0,   0.5,   0.5), (1.0/3 * 2, 0,   1.0/3, 0.5), (1.0/3, 0,   1.0/3 * 2, 0.5)),
    'bottom-left'    : ((0,     0.5, 0.5,   0.5), (0,         0.5, 1.0/3, 0.5), (0,     0.5, 1.0/3 * 2, 0.5)),
    'bottom-right'   : ((0.5,   0.5, 0.5,   0.5), (1.0/3 * 2, 0.5, 1.0/3, 0.5), (1.0/3, 0.5, 1.0/3 * 2, 0.5)),
    'maximize'       : toggleMaximize,
    'monitor-switch' : cycleMonitors,
}

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
    }

class WindowManager(object):
    """Once completed, this will be the new, cleaner way to manipulate windows."""
    def get_active_window():
        """
        Retrieve the active window.

        Returns None of the _NET_ACTIVE_WINDOW hint isn't supported or if the
        active window is the desktop.
        """
        # Get the root and active window
        root = gtk.gdk.screen_get_default()
        if root.supports_net_wm_hint("_NET_ACTIVE_WINDOW") and root.supports_net_wm_hint("_NET_WM_WINDOW_TYPE"):
            win = root.get_active_window()
        else:
            return None

        # Do nothing if the desktop is the active window
        if win.property_get("_NET_WM_WINDOW_TYPE")[-1][0] == '_NET_WM_WINDOW_TYPE_DESKTOP':
            return None

        return win

    def get_frame_dimensions(win):
        """Given a window, return a (border, titlebar) thickness tuple."""
        _or, _ror = win.get_origin(), win.get_root_origin()
        return _or[0] - _ror[0], _or[1] - _ror[1]

    def get_combined_dimensions(win):
        """Given a window, return the rectangle for its dimensions (frame
        included) relative to the monitor and the rectangle for the monitor in
        question."""
        # Calculate the size of the wm decorations
        winw, winh = win.get_geometry()[2:4]
        border, titlebar = self.get_frame_dimensions(win)
        w, h = winw + (border*2), winh + (titlebar+border)

        # Calculate the position of where the wm decorations start (not the window itself)
        screenposx, screenposy = win.get_root_origin()

        # Adjust the position to make it relative to the monitor rather than
        # the desktop
        #FIXME: How do I retrieve the root window from a given one?
        monitorID = root.get_monitor_at_window(win)
        monitorGeom = root.get_monitor_geometry(monitorID)
        winGeom = gtk.gdk.Rectangle(screenposx - monitorGeom.x,
                screenposy - monitorGeom.y, w, h)

        return monitorGeom, winGeom

    def reposition(win, geom, monitor=gtk.gdk.Rectangle(0,0,0,0)):
        """
        Position and size a window, decorations inclusive, according to the
        provided target window and monitor geometry rectangles.

        If no monitor rectangle is specified, position relative to the desktop
        as a whole.
        """
        border, titlebar = get_frame_dimensions(win)
        win.move_resize(geom.x + monitor.x, geom.y + monitor.y,
                geom.width - (border * 2), geom.height - (titlebar + border))


def get_frame_thickness(win):
    """Given a window, return a (border, titlebar) thickness tuple."""
    _or, _ror = win.get_origin(), win.get_root_origin()
    return _or[0] - _ror[0], _or[1] - _ror[1]

def positionWindow(win, geom, monitor = gtk.gdk.Rectangle(0,0,0,0)):
    """
    Position and size a window, decorations inclusive.

    The optional monitor argument allows use with geometry rectangles
    where the monitor offest hasn't been pre-calculated.
    """
    border, titlebar = get_frame_thickness(win)
    win.move_resize(geom.x + monitor.x, geom.y + monitor.y,
            geom.width - (border * 2), geom.height - (titlebar + border))

def getGeometries(win=None):
    """
    Get the geometry for the given window (including window decorations) and
    the monitor it's on. If not window is specified, the active window is used.

    Window geometry is relative to the monitor, not the desktop.

    Returns a tuple of the window object, two gtk.gdk.Rectangle objects
    containing the monitor and window geometry, respectively, and the monitor ID
    (for multi-head desktops).

    Returns (None, None, None) if the specified window is a desktop window or
    if no window was specified and _NET_ACTIVE_WINDOW is unsupported.
    """
    # Get the root and active window
    root = gtk.gdk.screen_get_default()
    if root.supports_net_wm_hint("_NET_ACTIVE_WINDOW") and root.supports_net_wm_hint("_NET_WM_WINDOW_TYPE"):
        win = win or root.get_active_window()
    elif not win:
        return None, None, None

    # Do nothing if the desktop is the active window
    if win.property_get("_NET_WM_WINDOW_TYPE")[-1][0] == '_NET_WM_WINDOW_TYPE_DESKTOP':
        return None, None, None

    # Calculate the size of the wm decorations
    winw, winh = win.get_geometry()[2:4]
    border, titlebar = get_frame_thickness(win)
    w, h = winw + (border*2), winh + (titlebar+border)

    # Calculate the position of where the wm decorations start (not the window itself)
    screenposx, screenposy = win.get_root_origin()

    monitorID = root.get_monitor_at_window(win)
    monitorGeom = root.get_monitor_geometry(monitorID)
    winGeom = gtk.gdk.Rectangle(screenposx - monitorGeom.x,
            screenposy - monitorGeom.y, w, h)

    return win, monitorGeom, winGeom, monitorID

def cycleDimensions(dimensions, window=None):
    """
    Given a window and a list of 4-tuples containing dimensions as a decimal
    percentage of monitor size, cycle through the list, taking one step each
    time this function is called.

    If the window's dimensions are not in the list, set them to the first list
    entry.

    Returns the chosen gtk.gdk.Rectangle.
    """
    win, monitorG, winG = getGeometries(window)[0:3]

    dims = []
    for tup in dimensions:
        dims.append((int(tup[0] * monitorG.width),
                     int(tup[1] * monitorG.height),
                     int(tup[2] * monitorG.width),
                     int(tup[3] * monitorG.height)))

    result = gtk.gdk.Rectangle(*dims[0])
    for pos, val in enumerate(dims):
        if tuple(winG) == tuple(val):
            result = gtk.gdk.Rectangle(*dims[(pos + 1) % len(dims)])
            break

    positionWindow(win, result, monitorG)

def doCommand(command):
    """Resolve a textual positioning command and execute it."""
    command = positions[command]
    if isinstance(command, (tuple, list)):
        cycleDimensions(command)
    else:
        command()

if __name__ == '__main__':
    from optparse import OptionParser
    parser = OptionParser(usage="%prog [options] [arguments]",
            version="%%prog v%s" % __version__)
    parser.add_option('-b', '--bindkeys', action="store_true", dest="daemonize",
        default=False, help="Use python-xlib to set up keybindings and then wait.")
    parser.add_option('--valid-args', action="store_true", dest="showArgs",
        default=False, help="List valid arguments for use without --bindkeys.")

    opts, args = parser.parse_args()

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
            for x in range(0, handle.pending_events()):
                xevent = handle.next_event()
                if xevent.type == X.KeyPress:
                    keycode = xevent.detail
                    doCommand(keys[keycode])
            return True

        # Merge python-xlib into the Glib event loop and start things going.
        gobject.io_add_watch(root.display, gobject.IO_IN, handle_xevent)
        gtk.main()
    elif not opts.daemonize:
        badArgs = [x for x in args if x not in positions]
        if not args or badArgs or opts.showArgs:
            # sorted() was added in 2.4 and everything else should be 2.3-safe.
            validArgs = list(positions)
            validArgs.sort()

            if badArgs:
                print "Invalid argument(s): %s" % ' '.join(badArgs)
            print "Valid arguments are: \n\t%s" % '\n\t'.join(validArgs)
            if not opts.showArgs:
                print "\nUse --help for a list of valid options."
                sys.exit(errno.ENOENT)

        for arg in args:
            doCommand(args[0])
        while gtk.events_pending():
            gtk.main_iteration()

