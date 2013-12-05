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

@todo 1.0.0: Retire L{KEYLOOKUP}. (API-breaking change)

@newfield appname: Application Name
"""

__appname__ = "QuickTile"
__author__  = "Stephan Sokolow (deitarion/SSokolow)"
__version__ = "0.2.2"
__license__ = "GNU GPL 2.0 or later"

import errno, logging, os, sys, time
from ConfigParser import RawConfigParser
from heapq import heappop, heappush
from itertools import chain, combinations
from functools import wraps
from UserDict import DictMixin

# TODO: Decide on a way to test this since Nose can't.
#: Used to filter spurious libwnck error messages from stderr since PyGTK
#: doesn't expose g_log_set_handler() to allow proper filtering.
if __name__ == '__main__':  # pragma: nocover
    import subprocess
    glib_log_filter = subprocess.Popen(
            ['grep', '-v', 'Unhandled action type _OB_WM'],
            stdin=subprocess.PIPE)

    # Redirect stderr through grep
    os.dup2(glib_log_filter.stdin.fileno(), sys.stderr.fileno())

import pygtk
pygtk.require('2.0')

import gtk, gobject, wnck

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
wnck.set_client_type(wnck.CLIENT_TYPE_PAGER)

try:
    from Xlib import X
    from Xlib.display import Display
    from Xlib.error import BadAccess
    XLIB_PRESENT = True  #: Indicates presence of python-xlib (runtime check)
except ImportError:
    XLIB_PRESENT = False  #: Indicates presence of python-xlib (runtime check)

DBUS_PRESENT = False  #: Indicates availability of D-Bus (runtime check)
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
        sessBus = SessionBus()  #: D-Bus Session Bus for L{QuickTileApp.run}
    except DBusException:
        pass
    else:
        DBUS_PRESENT = True  #: Indicates availability of D-Bus (runtime check)

#: Location for config files (determined at runtime).
XDG_CONFIG_DIR = os.environ.get('XDG_CONFIG_HOME',
                                os.path.expanduser('~/.config'))
#{ Settings

class GravityLayout(object):
    """Helper for generating L{cycle_dimensions} presets."""
    #: Possible window alignments relative to the monitor/desktop.
    #: @todo 1.0.0: Normalize these to X11 or CSS terminology for 1.0
    #:     (API-breaking change)
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
    }

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

# Keep these temporary variables out of the API docs
del col, grav, gv, x

DEFAULTS = {
    'general': {
        # Use Ctrl+Alt as the default base for key combinations
        'ModMask': '<Ctrl><Alt>',
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
    """C{powerset([1,2,3])} --> C{() (1,) (2,) (3,) (1,2) (1,3) (2,3) (1,2,3)}

    @rtype: iterable
    """
    s = list(iterable)
    return chain.from_iterable(combinations(s, r) for r in range(len(s) + 1))

def fmt_table(rows, headers, group_by=None):
    """Format a collection as a textual table.

    @param headers: Header labels for the columns
    @param group_by: Index of the column to group results by.
    @type rows: C{dict} or iterable of iterables
    @type headers: C{list(str)}
    @type group_by: C{int}

    @attention: This uses C{zip()} to combine things. The number of columns
        displayed will be defined by the narrowest of all rows.

    @rtype: C{str}
    """
    output = []

    if isinstance(rows, dict):
        rows = list(sorted(rows.items()))

    groups = {}
    if group_by is not None:
        headers = list(headers)
        headers.pop(group_by)
        rows = [list(row) for row in rows]
        for row in rows:
            group = row.pop(group_by)
            groups.setdefault(group, []).append(row)
    else:
        groups[''] = rows

    # Identify how much space needs to be allocated for each column
    col_maxlens = []
    for pos, header in enumerate(headers):
        maxlen = max(len(x[pos]) for x in rows if len(x) > pos)
        col_maxlens.append(max(maxlen, len(header)))

    def fmt_row(row, pad=' ', indent=0, min_width=0):
        result = []
        for width, label in zip(col_maxlens, row):
            result.append('%s%s ' % (' ' * indent, label.ljust(width, pad)))

        _w = sum(len(x) for x in result)
        if _w < min_width:
            result[-1] = result[-1][:-1]
            result.append(pad * (min_width - _w + 1))

        result.append('\n')
        return result

    # Print the headers and divider
    group_width = max(len(x) for x in groups)
    output.extend(fmt_row(headers))
    output.extend(fmt_row([''] * len(headers), '-', min_width=group_width + 1))

    for group in sorted(groups):
        if group:
            output.append("\n%s\n" % group)
        for row in groups[group]:
            output.extend(fmt_row(row, indent=1))

    return ''.join(output)

class EnumSafeDict(DictMixin):
    """A dict-like object which avoids comparing objects of different types
    to avoid triggering spurious Glib "comparing different enum types"
    warnings.
    """

    def __init__(self, *args):
        self._contents = {}

        for inDict in args:
            for key, val in inDict.items():
                self[key] = val

    def __contains__(self, key):
        ktype = type(key)
        return ktype in self._contents and key in self._contents[ktype]

    def __delitem__(self, key):
        if key in self:
            ktype = type(key)
            section = self._contents[ktype]
            del section[key]
            if not section:
                del self._contents[ktype]
        else:
            raise KeyError(key)

    def __getitem__(self, key):
        if key in self:
            return self._contents[type(key)][key]
        else:
            raise KeyError(key)

    def __iter__(self):
        for section in self._contents.values():
            for key in section.keys():
                yield key

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__,
            ', '.join(repr(x) for x in self._contents.values()))

    def __setitem__(self, key, value):
        ktype = type(key)
        self._contents.setdefault(ktype, {})[key] = value

    def iteritems(self):
        return [(key, self[key]) for key in self]

    def keys(self):
        return list(self)

#}

class CommandRegistry(object):
    """Handles lookup and boilerplate for window management commands.

    Separated from WindowManager so its lifecycle is not tied to a specific
    GDK Screen object.
    """

    def __init__(self):
        self.commands = {}
        self.help = {}

    def __iter__(self):
        for x in self.commands:
            yield x

    def __str__(self):
        return fmt_table(self.help, ('Known Commands', 'desc'), group_by=1)

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

            helpStr = func.__doc__.strip().split('\n')[0].split('. ')[0]
            self.help[name] = helpStr.strip('.')

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

    #: Lookup table for internal window gravity support.
    #: (libwnck's support is either unreliable or broken)
    gravities = EnumSafeDict({
        'NORTH_WEST': (0.0, 0.0),
        'NORTH': (0.5, 0.0),
        'NORTH_EAST': (1.0, 0.0),
        'WEST': (0.0, 0.5),
        'CENTER': (0.5, 0.5),
        'EAST': (1.0, 0.5),
        'SOUTH_WEST': (0.0, 1.0),
        'SOUTH': (0.5, 1.0),
        'SOUTH_EAST': (1.0, 1.0),
    })
    key, val = None, None  # Safety cushion for the "del" line.
    for key, val in gravities.items():
        del gravities[key]

        # Support GDK gravity constants
        gravities[getattr(gtk.gdk, 'GRAVITY_%s' % key)] = val

        # Support libwnck gravity constants
        _name = 'WINDOW_GRAVITY_%s' % key.replace('_', '')
        gravities[getattr(wnck, _name)] = val

    # Prevent these temporary variables from showing up in the apidocs
    del _name, key, val

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

    @classmethod
    def calc_win_gravity(cls, geom, gravity):
        """Calculate the X and Y coordinates necessary to simulate non-topleft
        gravity on a window.

        @param geom: The window geometry to which to apply the corrections.
        @param gravity: A desired gravity chosen from L{gravities}.
        @type geom: C{gtk.gdk.Rectangle}
        @type gravity: C{wnck.WINDOW_GRAVITY_*} or C{gtk.gdk.GRAVITY_*}

        @returns: The coordinates to be used to achieve the desired position.
        @rtype: C{(x, y)}
        """
        grav_x, grav_y = cls.gravities[gravity]

        return (
            int(geom.x - (geom.width * grav_x)),
            int(geom.y - (geom.height * grav_y))
        )

    @staticmethod
    def get_geometry_rel(window, monitor_geom):
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

    @staticmethod
    def get_monitor(win):
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

        struts = []
        if self.gdk_screen.supports_net_wm_hint("_NET_WM_STRUT_PARTIAL"):
            # Gather all struts
            struts.append(rootWin.property_get("_NET_WM_STRUT_PARTIAL"))
            if (self.gdk_screen.supports_net_wm_hint("_NET_CLIENT_LIST")):
                # Source: http://stackoverflow.com/a/11332614/435253
                for wid in rootWin.property_get('_NET_CLIENT_LIST')[2]:
                    w = gtk.gdk.window_foreign_new(wid)
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

    def get_workspace(self, window=None, direction=None):
        """Get a workspace relative to either a window or the active one.

        @param window: The point of reference. C{None} for the active workspace
        @param direction: The direction in which to look, relative to the point
            of reference. Accepts the following types:
             - C{wnck.MotionDirection}: Non-cycling direction
             - C{int}: Relative index in the list of workspaces
             - C{None}: Just get the workspace object for the point of
               reference

        @type window: C{wnck.Window} or C{None}
        @rtype: C{wnck.Workspace} or C{None}
        @returns: The workspace object or C{None} if no match could be found.
        """
        if window:
            cur = window.get_workspace()
        else:
            cur = self.screen.get_active_workspace()

        if not cur:
            return None  # It's either pinned or on no workspaces

        if isinstance(direction, wnck.MotionDirection):
            nxt = cur.get_neighbor(direction)
        elif isinstance(direction, int):
            nxt = wm.screen.get_workspace((cur.get_number() + direction) %
                    wm.screen.get_workspace_count())
        elif direction is None:
            nxt = cur
        else:
            nxt = None
            logging.warn("Unrecognized direction: %r", direction)

        return nxt

    @classmethod
    def reposition(cls, win, geom=None, monitor=gtk.gdk.Rectangle(0, 0, 0, 0),
            keep_maximize=False, gravity=wnck.WINDOW_GRAVITY_NORTHWEST,
            geometry_mask= wnck.WINDOW_CHANGE_X | wnck.WINDOW_CHANGE_Y |
                wnck.WINDOW_CHANGE_WIDTH | wnck.WINDOW_CHANGE_HEIGHT):
        """
        Position and size a window, decorations inclusive, according to the
        provided target window and monitor geometry rectangles.

        If no monitor rectangle is specified, position relative to the desktop
        as a whole.

        @param win: The C{wnck.Window} to operate on.
        @param geom: The new geometry for the window. Can be left unspecified
            if the intent is to move the window to another monitor without
            repositioning it.
        @param monitor: The frame relative to which C{geom} should be
            interpreted. The whole desktop if unspecified.
        @param keep_maximize: Whether to re-maximize a maximized window after
            un-maximizing it to move it.
        @param gravity: A constant specifying which point on the window is
            referred to by the X and Y coordinates in C{geom}.
        @param geometry_mask: A set of flags determining which aspects of the
            requested geometry should actually be applied to the window.
            (Allows the same geometry definition to easily be shared between
            operations like move and resize.)
        @type win: C{gtk.gdk.Window}
        @type geom: C{gtk.gdk.Rectangle}
        @type monitor: C{gtk.gdk.Rectangle}
        @type keep_maximize: C{bool}
        @type gravity: U{WnckWindowGravity<https://developer.gnome.org/libwnck/stable/WnckWindow.html#WnckWindowGravity>} or U{GDK Gravity Constant<http://www.pygtk.org/docs/pygtk/gdk-constants.html#gdk-gravity-constants>}
        @type geometry_mask: U{WnckWindowMoveResizeMask<https://developer.gnome.org/libwnck/2.30/WnckWindow.html#WnckWindowMoveResizeMask>}

        @todo 1.0.0: Look for a way to accomplish this with a cleaner method
            signature. This is getting a little hairy. (API-breaking change)
        """

        # We need to ensure that ignored values are still present for
        # gravity calculations.
        old_geom = wm.get_geometry_rel(win, wm.get_monitor(win)[1])
        if geom:
            for attr in ('x', 'y', 'width', 'height'):
                if not geometry_mask & getattr(wnck,
                        'WINDOW_CHANGE_%s' % attr.upper()):
                    setattr(geom, attr, getattr(old_geom, attr))
        else:
            geom = old_geom

        # Unmaximize and record the types we may need to restore
        max_types, maxed = ['', '_horizontally', '_vertically'], []
        for mt in max_types:
            if getattr(win, 'is_maximized' + mt)():
                maxed.append(mt)
                getattr(win, 'unmaximize' + mt)()

        # Apply gravity and resolve to absolute desktop coordinates.
        new_x, new_y = cls.calc_win_gravity(geom, gravity)
        new_x += monitor.x
        new_y += monitor.y

        logging.debug("repositioning to (%d, %d, %d, %d)",
                new_x, new_y, geom.width, geom.height)

        #XXX: I'm not sure whether wnck, Openbox, or both are at fault,
        #     but window gravities seem to have no effect beyond double-
        #     compensating for window border thickness unless using
        #     WINDOW_GRAVITY_STATIC.
        #
        #     My best guess is that the gravity modifiers are being applied
        #     to the window frame rather than the window itself, hence why
        #     static gravity would position correctly and north-west gravity
        #     would double-compensate for the titlebar and border dimensions.
        #
        #     ...however, that still doesn't explain why the non-topleft
        #     gravities have no effect. I'm guessing something's just broken.
        win.set_geometry(wnck.WINDOW_GRAVITY_STATIC, geometry_mask,
                new_x, new_y, geom.width, geom.height)

        # Restore maximization if asked
        if maxed and keep_maximize:
            for mt in maxed:
                getattr(win, 'maximize' + mt)()

class KeyBinder(object):
    """A convenience class for wrapping C{XGrabKey}."""

    #: @todo: Figure out how to set the modifier mask in X11 and use
    #:        C{gtk.accelerator_get_default_mod_mask()} to feed said code.
    ignored_modifiers = ['Mod2Mask', 'LockMask']

    #: Used to pass state from L{handle_xerror}
    keybind_failed = False

    def __init__(self, xdisplay=None):
        """Connect to X11 and the Glib event loop.

        @param xdisplay: A C{python-xlib} display handle.
        @type xdisplay: C{Xlib.display.Display}
        """
        self.xdisp = xdisplay or Display()
        self.xroot = self.xdisp.screen().root
        self._keys = {}

        # Resolve these at runtime to avoid NameErrors
        self.ignored_modifiers = [getattr(X, name) for name in
                self.ignored_modifiers]

        # We want to receive KeyPress events
        self.xroot.change_attributes(event_mask=X.KeyPressMask)

        # Set up a handler to catch XGrabKey() failures
        self.xdisp.set_error_handler(self.handle_xerror)

        # Merge python-xlib into the Glib event loop
        # Source: http://www.pygtk.org/pygtk2tutorial/sec-MonitoringIO.html
        gobject.io_add_watch(self.xroot.display,
                             gobject.IO_IN, self.handle_xevent)

    def bind(self, accel, callback):
        """Bind a global key combination to a callback.

        @param accel: An accelerator as either a string to be parsed by
            C{gtk.accelerator_parse()} or a tuple as returned by it.)
        @param callback: The function to call when the key is pressed.

        @type accel: C{str} or C{(int, gtk.gdk.ModifierType)} or C{(int, int)}
        @type callback: C{function}

        @returns: A boolean indicating whether the provided keybinding was
            parsed successfully. (But not whether it was registered
            successfully due to the asynchronous nature of the C{XGrabKey}
            request.)
        @rtype: C{bool}
        """
        if isinstance(accel, basestring):
            keysym, modmask = gtk.accelerator_parse(accel)
        else:
            keysym, modmask = accel

        if not gtk.accelerator_valid(keysym, modmask):
            logging.error("Invalid keybinding: %s", accel)
            return False

        # Convert to what XGrabKey expects
        keycode = self.xdisp.keysym_to_keycode(keysym)
        if isinstance(modmask, gtk.gdk.ModifierType):
            modmask = modmask.real

        # Ignore modifiers like Mod2 (NumLock) and Lock (CapsLock)
        for mmask in self._vary_modmask(modmask, self.ignored_modifiers):
            self._keys.setdefault(keycode, []).append((mmask, callback))
            self.xroot.grab_key(keycode, mmask,
                    1, X.GrabModeAsync, X.GrabModeAsync)

        # If we don't do this, then nothing works.
        # I assume it flushes the XGrabKey calls to the server.
        self.xdisp.sync()

        if self.keybind_failed:
            self.keybind_failed = False
            logging.warning("Failed to bind key. It may already be in use: %s",
                accel)

    def handle_xerror(self, err, req=None):  # pylint: disable=W0613
        """Used to identify when attempts to bind keys fail.
        @note: If you can make python-xlib's C{CatchError} actually work or if
               you can retrieve more information to show, feel free.
        """
        if isinstance(err, BadAccess):
            self.keybind_failed = True
        else:
            self.xdisp.display.default_error_handler(err)

    def handle_xevent(self, src, cond, handle=None):  # pylint: disable=W0613
        """Dispatch C{XKeyPress} events to their callbacks.

        @rtype: C{True}

        @todo: Make sure uncaught exceptions are prevented from making
            quicktile unresponsive in the general case.
        """
        handle = handle or self.xroot.display

        for _ in range(0, handle.pending_events()):
            xevent = handle.next_event()
            if xevent.type == X.KeyPress:
                if xevent.detail in self._keys:
                    for mmask, cb in self._keys[xevent.detail]:
                        if mmask == xevent.state:
                            cb()
                            break
                        elif mmask == 0:
                            logging.debug("X11 returned null modifier!")
                            cb()
                            break
                    else:
                        logging.error("Received an event for a recognized key "
                                  "with unrecognized modifiers: %s, %s",
                                  xevent.detail, xevent.state)

                else:
                    logging.error("Received an event for an unrecognized "
                                  "keybind: %s, %s", xevent.detail, mmask)

        # Necessary for proper function
        return True

    @staticmethod
    def _vary_modmask(modmask, ignored):
        """Generate all possible variations on C{modmask} that need to be
        taken into consideration if we can't properly ignore the modifiers in
        C{ignored}. (Typically NumLock and CapsLock)

        @param modmask: A bitfield to be combinatorically grown.
        @param ignored: Modifiers to be combined with C{modmask}.

        @type modmask: C{int} or C{gtk.gdk.ModifierType}
        @type ignored: C{list(int)}

        @rtype: generator of C{type(modmask)}
        """

        for ignored in powerset(ignored):
            imask = reduce(lambda x, y: x | y, ignored, 0)
            yield modmask | imask

class QuickTileApp(object):
    """The basic Glib application itself."""

    def __init__(self, wm, commands, keys=None, modmask=None):
        """Populate the instance variables.

        @param keys: A dict mapping X11 keysyms to L{CommandRegistry}
            command names.
        @param modmask: A modifier mask to prefix to all keybindings.
        @type wm: The L{WindowManager} instance to use.
        @type keys: C{dict}
        @type modmask: C{GdkModifierType}
        """
        self.wm = wm
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

        if XLIB_PRESENT:
            self.keybinder = KeyBinder()
            for key, func in self._keys.items():
                self.keybinder.bind(self._modmask + key,
                        lambda func=func: self.commands.call(func, wm))
        else:
            logging.error("Could not find python-xlib. Cannot bind keys.")

        if DBUS_PRESENT:
            class QuickTile(dbus.service.Object):
                def __init__(self, commands):
                    dbus.service.Object.__init__(self, sessBus,
                                                 '/com/ssokolow/QuickTile')
                    self.commands = commands

                @dbus.service.method(dbus_interface='com.ssokolow.QuickTile',
                         in_signature='s', out_signature='b')
                def doCommand(self, command):
                    return self.commands.call(command, wm)

            self.dbusName = dbus.service.BusName("com.ssokolow.QuickTile",
                                                 sessBus)
            self.dbusObj = QuickTile(self.commands)
        else:
            logging.warn("Could not connect to the D-Bus Session Bus.")

        if (XLIB_PRESENT or DBUS_PRESENT):
            gtk.main()
            return True
        else:
            return False

    def showBinds(self):
        """Print a formatted readout of defined keybindings and the modifier
        mask to stdout.

        @todo: Look into moving this into L{KeyBinder}
        """

        print "Keybindings defined for use with --daemonize:\n"
        print "Modifier: %s\n" % self._modmask
        print fmt_table(self._keys, ('Key', 'Action'))

#: The instance of L{CommandRegistry} to be used in 99.9% of use cases.
commands = CommandRegistry()
#{ Tiling Commands

@commands.addMany(POSITIONS)
def cycle_dimensions(wm, win, state, *dimensions):
    """Cycle the active window through a list of positions and shapes.

    Takes one step each time this function is called.

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
@commands.add('monitor-next', 1)
@commands.add('monitor-prev', -1)
def cycle_monitors(wm, win, state, step=1):
    """Cycle the active window between monitors while preserving position.

    @todo 1.0.0: Remove C{monitor-switch} in favor of C{monitor-next}
        (API-breaking change)
    """
    mon_id = state['monitor_id']
    new_mon_id = (mon_id + step) % wm.gdk_screen.get_n_monitors()

    new_mon_geom = wm.gdk_screen.get_monitor_geometry(new_mon_id)
    logging.debug("Moving window to monitor %s", new_mon_id)

    wm.reposition(win, None, new_mon_geom, keep_maximize=True)

@commands.add('move-to-center')
def cmd_moveCenter(wm, win, state):
    """Center the window in the monitor it currently occupies."""
    use_rect = state['usable_rect']

    dims = (int(use_rect.width / 2), int(use_rect.height / 2), 0, 0)
    logging.debug("dims %r", dims)

    result = gtk.gdk.Rectangle(*dims)
    logging.debug("result %r", tuple(result))

    wm.reposition(win, result, use_rect, gravity=wnck.WINDOW_GRAVITY_CENTER,
           geometry_mask= wnck.WINDOW_CHANGE_X | wnck.WINDOW_CHANGE_Y)

@commands.add('bordered')
def toggle_decorated(wm, win, state):  # pylint: disable=W0613
    """Toggle window state on the active window."""
    win = gtk.gdk.window_foreign_new(win.get_xid())
    win.set_decorations(not win.get_decorations())

@commands.add('show-desktop')
def toggle_desktop(wm, win, state):  # pylint: disable=W0613
    """Toggle "all windows minimized" to view the desktop"""
    target = not wm.screen.get_showing_desktop()
    wm.screen.toggle_showing_desktop(target)

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
# pylint: disable=W0613
def toggle_state(wm, win, state, command, check, takes_bool=False):
    """Toggle window state on the active window.

    @param command: The C{wnck.Window} method name to be conditionally prefixed
        with "un", resolved, and called.
    @param check: The C{wnck.Window} method name to be called to check
        whether C{command} should be prefixed with "un".
    @param takes_bool: If C{True}, pass C{True} or C{False} to C{check} rather
        thank conditionally prefixing it with C{un} before resolving.
    @type command: C{str}
    @type check: C{str}
    @type takes_bool: C{bool}

    @todo 1.0.0: Rename C{vertical-maximize} and C{horizontal-maximize} to
        C{maximize-vertical} and C{maximize-horizontal}. (API-breaking change)
    """
    target = not getattr(win, check)()

    logging.debug('maximize: %s', target)
    if takes_bool:
        getattr(win, command)(target)
    else:
        getattr(win, ('' if target else 'un') + command)()

@commands.add('trigger-move', 'move')
@commands.add('trigger-resize', 'size')
def trigger_keyboard_action(wm, win, state, command):  # pylint: disable=W0613
    """Ask the Window Manager to begin a keyboard-driven operation."""
    getattr(win, 'keyboard_' + command)()

@commands.add('workspace-go-next', 1)
@commands.add('workspace-go-prev', -1)
@commands.add('workspace-go-up', wnck.MOTION_UP)
@commands.add('workspace-go-down', wnck.MOTION_DOWN)
@commands.add('workspace-go-left', wnck.MOTION_LEFT)
@commands.add('workspace-go-right', wnck.MOTION_RIGHT)
def workspace_go(wm, win, state, motion):  # pylint: disable=W0613
    """Switch the active workspace (next/prev wrap around)"""
    target = wm.get_workspace(None, motion)
    if not target:
        return  # It's either pinned, on no workspaces, or there is no match
    target.activate(int(time.time()))

@commands.add('workspace-send-next', 1)
@commands.add('workspace-send-prev', -1)
@commands.add('workspace-send-up', wnck.MOTION_UP)
@commands.add('workspace-send-down', wnck.MOTION_DOWN)
@commands.add('workspace-send-left', wnck.MOTION_LEFT)
@commands.add('workspace-send-right', wnck.MOTION_RIGHT)
def workspace_send_window(wm, win, state, motion):  # pylint: disable=W0613
    """Move the active window to another workspace (next/prev wrap around)"""
    target = wm.get_workspace(win, motion)
    if not target:
        return  # It's either pinned, on no workspaces, or there is no match

    win.move_to_workspace(target)

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

    mk_raw = modkeys = config.get('general', 'ModMask')
    if ' ' in modkeys.strip() and not '<' in modkeys:
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

    ignore_workarea = ((not config.getboolean('general', 'UseWorkarea'))
                       or opts.no_workarea)

    wm = WindowManager(ignore_workarea=ignore_workarea)
    app = QuickTileApp(wm, commands, keymap, modmask=modkeys)

    if opts.showBinds:
        app.showBinds()
        sys.exit()

    if opts.daemonize:
        if not app.run():
            logging.critical("Neither the Xlib nor the D-Bus backends were "
                             "available")
            sys.exit(errno.ENOENT)
            #FIXME: What's the proper exit code for "library not found"?

    elif not first_run:
        if not args or opts.showArgs:
            print commands

            if not opts.showArgs:
                print "\nUse --help for a list of valid options."
                sys.exit(errno.ENOENT)
        else:
            wm.screen.force_update()

            for arg in args:
                commands.call(arg, wm)
            while gtk.events_pending():
                gtk.main_iteration()
