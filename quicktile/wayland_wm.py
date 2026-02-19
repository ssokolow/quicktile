"""Window manager wrapper for Wayland using GNOME Shell D-Bus APIs"""

__author__ = "Julio Jiménez (juljimm)"
__license__ = "GNU GPL 2.0 or later"

import logging
import json
import os
import tempfile
from typing import Any, Dict, List, Optional, Tuple

import gi
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, Gio, GLib

from .util import Rectangle, UsableRegion


class WaylandWindow:
    """Wrapper for window data from Window Calls extension"""

    def __init__(self, data: Dict[str, Any], manager: 'WaylandWindowManager' = None):
        self._data = data
        self._id = data.get('id', 0)
        self._manager = manager

    @property
    def id(self) -> int:
        return self._id

    def get_xid(self) -> int:
        """Compatibility with X11 API"""
        return self._id

    def get_title(self) -> str:
        return self._data.get('title', '')

    def get_name(self) -> str:
        """Compatibility with Wnck.Window"""
        return self.get_title()

    def get_geometry(self) -> Tuple[int, int, int, int]:
        """Return (x, y, width, height)"""
        # First check if geometry is in data
        if self._data.get('width', 0) > 0:
            return (
                self._data.get('x', 0),
                self._data.get('y', 0),
                self._data.get('width', 0),
                self._data.get('height', 0)
            )
        # Otherwise fetch via D-Bus
        if self._manager:
            geom = self._manager.get_frame_rect(self._id)
            if geom:
                return geom
        return (0, 0, 0, 0)

    def is_maximized(self) -> bool:
        return self._data.get('maximized', False)

    def is_maximized_horizontally(self) -> bool:
        return self._data.get('maximized_horizontally', False)

    def is_maximized_vertically(self) -> bool:
        return self._data.get('maximized_vertically', False)

    def is_minimized(self) -> bool:
        return self._data.get('minimized', False)

    def is_fullscreen(self) -> bool:
        return self._data.get('fullscreen', False)

    def is_above(self) -> bool:
        return self._data.get('above', False)

    def is_below(self) -> bool:
        return self._data.get('below', False)

    def is_shaded(self) -> bool:
        return False  # Not typically available in Wayland

    def is_pinned(self) -> bool:
        return self._data.get('on_all_workspaces', False)

    def has_focus(self) -> bool:
        return self._data.get('focus', False)

    def get_workspace(self):
        return self._data.get('workspace', None)

    def get_window_type(self):
        return self._data.get('wm_class', '')

    # Action methods - delegate to manager
    def maximize(self):
        if self._manager:
            self._manager.maximize(self)

    def unmaximize(self):
        if self._manager:
            self._manager.unmaximize(self)

    def minimize(self):
        if self._manager:
            self._manager.minimize(self)

    def unminimize(self):
        if self._manager:
            self._manager.activate(self)

    def maximize_horizontally(self):
        """Maximize window horizontally (full width, keep height)"""
        if self._manager:
            self._manager.maximize_horizontally(self)

    def unmaximize_horizontally(self):
        """Restore window from horizontal maximize"""
        if self._manager:
            self._manager.unmaximize_horizontally(self)

    def maximize_vertically(self):
        """Maximize window vertically (full height, keep width)"""
        if self._manager:
            self._manager.maximize_vertically(self)

    def unmaximize_vertically(self):
        """Restore window from vertical maximize"""
        if self._manager:
            self._manager.unmaximize_vertically(self)

    def set_fullscreen(self, state: bool):
        logging.warning("set_fullscreen not fully implemented in Wayland")

    def make_above(self):
        logging.warning("make_above not available in Wayland")

    def unmake_above(self):
        logging.warning("unmake_above not available in Wayland")

    def make_below(self):
        logging.warning("make_below not available in Wayland")

    def unmake_below(self):
        logging.warning("unmake_below not available in Wayland")

    def shade(self):
        logging.warning("shade not available in Wayland")

    def unshade(self):
        logging.warning("unshade not available in Wayland")

    def pin(self):
        logging.warning("pin not available in Wayland")

    def unpin(self):
        logging.warning("unpin not available in Wayland")


class WaylandWindowManager:
    """Window manager for Wayland using Window Calls GNOME extension"""

    DBUS_NAME = "org.gnome.Shell"
    DBUS_PATH = "/org/gnome/Shell/Extensions/Windows"
    DBUS_INTERFACE = "org.gnome.Shell.Extensions.Windows"

    def __init__(self):
        self.usable_region = UsableRegion()
        self._proxy = None
        self._state_storage: Dict[int, Any] = {}
        self._state_file = self._get_state_file_path()
        self._panel_offsets = self._detect_panel_offsets()

        # Compatibility attributes
        self.gdk_screen = Gdk.Screen.get_default()
        self.gdk_display = self.gdk_screen.get_display() if self.gdk_screen else None

        self._init_dbus()
        self.update_geometry_cache()

    @staticmethod
    def _detect_dock_settings() -> Optional[Dict[str, Any]]:
        """Detect Ubuntu/GNOME dock configuration via GSettings.

        Checks that a dock extension (``ubuntu-dock`` or ``dash-to-dock``)
        is both installed *and* listed in the GNOME Shell enabled-extensions,
        then reads its position and icon size.

        Returns ``{'position': str, 'size': int}`` or ``None``.
        """
        # Map GSettings schema → possible extension UUIDs.
        # Ubuntu Dock is a fork of dash-to-dock and reuses its schema.
        dock_extensions = [
            ('org.gnome.shell.extensions.ubuntu-dock',
             ['ubuntu-dock@ubuntu.com']),
            ('org.gnome.shell.extensions.dash-to-dock',
             ['dash-to-dock@micxgx.gmail.com', 'ubuntu-dock@ubuntu.com']),
        ]

        schema_source = Gio.SettingsSchemaSource.get_default()
        if not schema_source:
            return None

        # Read the list of enabled extensions once
        enabled = set()
        shell_schema = schema_source.lookup('org.gnome.shell', True)
        if shell_schema:
            try:
                shell_settings = Gio.Settings.new('org.gnome.shell')
                enabled = set(shell_settings.get_strv('enabled-extensions'))
            except Exception:
                pass

        for schema_id, ext_uuids in dock_extensions:
            schema = schema_source.lookup(schema_id, True)
            if not schema:
                continue
            if enabled and not enabled.intersection(ext_uuids):
                logging.debug("Dock schema %s found but none of %s "
                              "enabled", schema_id, ext_uuids)
                continue
            try:
                settings = Gio.Settings.new(schema_id)
                position = settings.get_string('dock-position')
                icon_size = settings.get_int('dash-max-icon-size')
                dock_size = icon_size + 16

                logging.debug("Dock detected: position=%s, icon_size=%d, "
                              "dock_size=%d (schema=%s)",
                              position, icon_size, dock_size, schema_id)
                return {'position': position.upper(), 'size': dock_size}
            except Exception as e:
                logging.debug("Could not read dock settings from %s: %s",
                              schema_id, e)
        return None

    def _detect_panel_offsets(self) -> Dict[str, int]:
        """Detect offsets for all screen edges (top bar + dock).

        Strategy:
        1. Start from GDK ``get_workarea()`` vs ``get_geometry()`` deltas.
        2. Supplement with dock info from GSettings on any edge where GDK
           reported zero (GDK often detects the top bar but misses the dock).
        3. If GDK detected nothing at all, assume 32 px GNOME top bar.
        """
        offsets = {'top': 0, 'bottom': 0, 'left': 0, 'right': 0}
        gdk_detected_any = False

        display = Gdk.Display.get_default()
        if display and display.get_n_monitors() > 0:
            monitor = display.get_monitor(0)
            geom = monitor.get_geometry()
            workarea = monitor.get_workarea()

            gdk_top = workarea.y - geom.y
            gdk_bottom = (geom.y + geom.height) - (workarea.y + workarea.height)
            gdk_left = workarea.x - geom.x
            gdk_right = (geom.x + geom.width) - (workarea.x + workarea.width)

            if gdk_top or gdk_bottom or gdk_left or gdk_right:
                gdk_detected_any = True
                offsets = {
                    'top': max(gdk_top, 0),
                    'bottom': max(gdk_bottom, 0),
                    'left': max(gdk_left, 0),
                    'right': max(gdk_right, 0),
                }

        if not gdk_detected_any:
            offsets['top'] = 32

        # Supplement with dock from GSettings on edges GDK missed
        dock = self._detect_dock_settings()
        if dock:
            edge = dock['position'].lower()
            if edge in offsets and offsets[edge] == 0:
                offsets[edge] = dock['size']

        logging.debug("Panel offsets (gdk_detected=%s): %s",
                      gdk_detected_any, offsets)
        return offsets

    def _init_dbus(self):
        """Initialize D-Bus connection to Window Calls extension"""
        try:
            self._proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SESSION,
                Gio.DBusProxyFlags.NONE,
                None,
                self.DBUS_NAME,
                self.DBUS_PATH,
                self.DBUS_INTERFACE,
                None
            )
            # Validate that the extension is actually responding
            self._proxy.call_sync(
                'List', None, Gio.DBusCallFlags.NONE, -1, None)
            logging.info("Connected to Window Calls extension via D-Bus")
        except GLib.Error as e:
            logging.error("Failed to connect to Window Calls extension: %s", e)
            raise RuntimeError(
                "Window Calls extension not available. "
                "Please install it from: "
                "https://extensions.gnome.org/extension/4724/window-calls/"
            )

    # D-Bus method signatures for Window Calls extension
    DBUS_SIGNATURES = {
        'List': '',
        'MoveResize': 'uiiuu',  # winid, x, y, width, height
        'Move': 'uii',          # winid, x, y
        'Resize': 'uuu',        # winid, width, height
        'Maximize': 'u',
        'Unmaximize': 'u',
        'Minimize': 'u',
        'Unminimize': 'u',
        'Activate': 'u',
        'Close': 'u',
        'MoveToWorkspace': 'uu',
    }

    def _call_dbus(self, method: str, *args) -> Any:
        """Call a D-Bus method on the Window Calls extension"""
        try:
            if args:
                sig = self.DBUS_SIGNATURES.get(method, 'u' * len(args))
                result = self._proxy.call_sync(
                    method,
                    GLib.Variant('(' + sig + ')', args),
                    Gio.DBusCallFlags.NONE,
                    -1,
                    None
                )
            else:
                result = self._proxy.call_sync(
                    method,
                    None,
                    Gio.DBusCallFlags.NONE,
                    -1,
                    None
                )
            return result.unpack() if result else None
        except GLib.Error as e:
            logging.error("D-Bus call %s failed: %s", method, e)
            return None

    def update_geometry_cache(self):
        """Update monitor geometry cache"""
        display = Gdk.Display.get_default()
        if not display:
            logging.error("Could not get default display")
            return

        monitors = []
        n_monitors = display.get_n_monitors()

        for i in range(n_monitors):
            monitor = display.get_monitor(i)
            workarea = monitor.get_workarea()

            monitors.append(Rectangle(
                x=workarea.x,
                y=workarea.y,
                width=workarea.width,
                height=workarea.height
            ))

        if monitors:
            self.usable_region.set_monitors(monitors)
            self.usable_region.set_panels([])

        logging.debug("Loaded %d monitors for Wayland", len(monitors))

    def get_windows(self) -> List[WaylandWindow]:
        """Get list of all windows"""
        result = self._call_dbus("List")
        if not result:
            return []

        try:
            windows_data = json.loads(result[0]) if isinstance(result, tuple) else json.loads(result)
            return [WaylandWindow(w, self) for w in windows_data]
        except (json.JSONDecodeError, TypeError) as e:
            logging.error("Failed to parse window list: %s", e)
            return []

    def get_active_window(self) -> Optional[WaylandWindow]:
        """Get the currently focused window"""
        windows = self.get_windows()
        for win in windows:
            if win.has_focus():
                return win
        return windows[0] if windows else None

    def get_monitor(self, win: WaylandWindow) -> Tuple[int, Rectangle]:
        """Get the monitor containing the window"""
        x, y, w, h = win.get_geometry()
        center_x = x + w // 2
        center_y = y + h // 2

        display = Gdk.Display.get_default()
        if display:
            n_monitors = display.get_n_monitors()
            for i in range(n_monitors):
                monitor = display.get_monitor(i)
                geom = monitor.get_geometry()
                if (geom.x <= center_x < geom.x + geom.width and
                    geom.y <= center_y < geom.y + geom.height):
                    off = self._panel_offsets
                    return i, Rectangle(
                        x=geom.x + off['left'],
                        y=geom.y + off['top'],
                        width=geom.width - off['left'] - off['right'],
                        height=geom.height - off['top'] - off['bottom'],
                    )

        # Fallback to first monitor
        if self.usable_region._monitors:
            return 0, self.usable_region._monitors[0]
        return 0, Rectangle(0, 0, 1920, 1080)

    def reposition(self, win: WaylandWindow, geom: Optional[Rectangle] = None,
                   monitor: Rectangle = Rectangle(0, 0, 0, 0),
                   keep_maximize: bool = False, geometry_mask=None) -> None:
        """Move and resize a window"""
        if geom is None:
            return

        # Calculate absolute position
        new_x = monitor.x + geom.x if monitor.width > 0 else geom.x
        new_y = monitor.y + geom.y if monitor.height > 0 else geom.y
        new_w = geom.width
        new_h = geom.height

        logging.debug("Repositioning window %d to (%d, %d, %d, %d)",
                     win.id, new_x, new_y, new_w, new_h)

        # Call MoveResize via D-Bus
        self._call_dbus("MoveResize", win.id, new_x, new_y, new_w, new_h)

    def get_frame_rect(self, winid: int) -> Optional[Tuple[int, int, int, int]]:
        """Get window geometry via GetFrameRect D-Bus method"""
        try:
            result = self._proxy.call_sync(
                'GetFrameRect',
                GLib.Variant('(u)', (winid,)),
                Gio.DBusCallFlags.NONE,
                -1,
                None
            )
            if result:
                data = json.loads(result.unpack()[0])
                return (data.get('x', 0), data.get('y', 0),
                        data.get('width', 0), data.get('height', 0))
        except (GLib.Error, json.JSONDecodeError) as e:
            logging.error("GetFrameRect failed: %s", e)
        return None

    def maximize(self, win: WaylandWindow) -> None:
        """Maximize a window"""
        self._call_dbus("Maximize", win.id)

    def unmaximize(self, win: WaylandWindow) -> None:
        """Unmaximize a window"""
        self._call_dbus("Unmaximize", win.id)

    def minimize(self, win: WaylandWindow) -> None:
        """Minimize a window"""
        self._call_dbus("Minimize", win.id)

    def activate(self, win: WaylandWindow) -> None:
        """Activate/focus a window"""
        self._call_dbus("Activate", win.id)

    def _geometry_matches(self, current, expected, tolerance=10):
        """Check if current geometry matches expected within tolerance"""
        return (abs(current[0] - expected['x']) <= tolerance and
                abs(current[1] - expected['y']) <= tolerance and
                abs(current[2] - expected['w']) <= tolerance and
                abs(current[3] - expected['h']) <= tolerance)

    def maximize_vertically(self, win: WaylandWindow) -> None:
        """Maximize window vertically (full height, keep width and x position)"""
        x, y, w, h = win.get_geometry()
        _, workarea = self.get_monitor(win)

        state_key = f"v_maximize_{win.id}"
        stored = self.get_property(win, state_key)

        # Calculate what the maximized geometry would be
        max_geom = {'x': x, 'y': workarea.y, 'w': w, 'h': workarea.height}

        if stored is not None:
            # Handle old format (just geometry) - clear it
            if 'maximized' not in stored:
                self.set_property(win, state_key, None)
                stored = None

        if stored is not None:
            # Check if window is still in maximized position
            if self._geometry_matches((x, y, w, h), stored['maximized']):
                # Window unchanged - restore original
                self._call_dbus("MoveResize", win.id, stored['original']['x'],
                               stored['original']['y'], stored['original']['w'],
                               stored['original']['h'])
                self.set_property(win, state_key, None)
                return
            else:
                # Window was moved/resized by user - clear state
                self.set_property(win, state_key, None)

        # Save current as original and maximize
        self.set_property(win, state_key, {
            'original': {'x': x, 'y': y, 'w': w, 'h': h},
            'maximized': max_geom
        })
        self._call_dbus("MoveResize", win.id, max_geom['x'], max_geom['y'],
                       max_geom['w'], max_geom['h'])

    def unmaximize_vertically(self, win: WaylandWindow) -> None:
        """Restore window from vertical maximize"""
        state_key = f"v_maximize_{win.id}"
        stored = self.get_property(win, state_key)
        if stored and 'original' in stored:
            self._call_dbus("MoveResize", win.id, stored['original']['x'],
                           stored['original']['y'], stored['original']['w'],
                           stored['original']['h'])
        self.set_property(win, state_key, None)

    def maximize_horizontally(self, win: WaylandWindow) -> None:
        """Maximize window horizontally (full width, keep height and y position)"""
        x, y, w, h = win.get_geometry()
        _, workarea = self.get_monitor(win)

        state_key = f"h_maximize_{win.id}"
        stored = self.get_property(win, state_key)

        # Calculate what the maximized geometry would be
        max_geom = {'x': workarea.x, 'y': y, 'w': workarea.width, 'h': h}

        if stored is not None:
            # Handle old format (just geometry) - clear it
            if 'maximized' not in stored:
                self.set_property(win, state_key, None)
                stored = None

        if stored is not None:
            # Check if window is still in maximized position
            if self._geometry_matches((x, y, w, h), stored['maximized']):
                # Window unchanged - restore original
                self._call_dbus("MoveResize", win.id, stored['original']['x'],
                               stored['original']['y'], stored['original']['w'],
                               stored['original']['h'])
                self.set_property(win, state_key, None)
                return
            else:
                # Window was moved/resized by user - clear state
                self.set_property(win, state_key, None)

        # Save current as original and maximize
        self.set_property(win, state_key, {
            'original': {'x': x, 'y': y, 'w': w, 'h': h},
            'maximized': max_geom
        })
        self._call_dbus("MoveResize", win.id, max_geom['x'], max_geom['y'],
                       max_geom['w'], max_geom['h'])

    def unmaximize_horizontally(self, win: WaylandWindow) -> None:
        """Restore window from horizontal maximize"""
        state_key = f"h_maximize_{win.id}"
        stored = self.get_property(win, state_key)
        if stored and 'original' in stored:
            self._call_dbus("MoveResize", win.id, stored['original']['x'],
                           stored['original']['y'], stored['original']['w'],
                           stored['original']['h'])
        self.set_property(win, state_key, None)

    def close(self, win: WaylandWindow) -> None:
        """Close a window"""
        self._call_dbus("Close", win.id)

    def move_to_workspace(self, win: WaylandWindow, workspace: int) -> None:
        """Move window to specified workspace"""
        self._call_dbus("MoveToWorkspace", win.id, workspace)

    # State storage (replaces X11 properties)

    def _get_state_file_path(self) -> str:
        """Determine the path for the state persistence file.

        Handles ``XDG_RUNTIME_DIR`` not being set and creates the
        containing directory with appropriate permissions per the
        `XDG Base Directory specification
        <https://wiki.archlinux.org/title/XDG_Base_Directory>`_.
        """
        runtime_dir = os.environ.get('XDG_RUNTIME_DIR')
        if runtime_dir and os.path.isdir(runtime_dir):
            state_dir = os.path.join(runtime_dir, 'quicktile')
        else:
            state_dir = os.path.join(
                tempfile.gettempdir(),
                'quicktile-{}'.format(os.getuid()))

        os.makedirs(state_dir, mode=0o700, exist_ok=True)
        path = os.path.join(state_dir, 'wayland-state.json')

        # Set sticky bit per XDG spec to prevent periodic cleanup
        try:
            os.chmod(state_dir, 0o1700)
        except OSError as err:
            logging.debug("Could not set sticky bit on %s: %s", state_dir, err)

        return path

    def _load_state(self) -> Dict:
        """Load state from file"""
        try:
            if os.path.exists(self._state_file):
                with open(self._state_file, 'r') as f:
                    state = json.load(f)
                # Touch the file to maintain mtime
                os.utime(self._state_file)
                return state
        except (json.JSONDecodeError, IOError) as e:
            logging.debug("Could not load state: %s", e)
        return {}

    def _save_state(self, state: Dict):
        """Save state to file"""
        try:
            with open(self._state_file, 'w') as f:
                json.dump(state, f)
        except IOError as e:
            logging.error("Could not save state: %s", e)

    def get_property(self, win, name: str, prop_type=None, empty=None):
        """Get stored property for window (uses file storage instead of X11)"""
        state = self._load_state()
        win_id = str(win.id if hasattr(win, 'id') else win)
        key = f"{win_id}:{name}"
        return state.get(key, empty)

    def set_property(self, win, name: str, value, prop_type=None, format_size=8):
        """Store property for window (uses file storage instead of X11)"""
        state = self._load_state()
        win_id = str(win.id if hasattr(win, 'id') else win)
        key = f"{win_id}:{name}"
        if value is None:
            state.pop(key, None)  # Remove key if value is None
        else:
            state[key] = value
        self._save_state(state)

    @staticmethod
    def is_relevant(window: WaylandWindow) -> bool:
        """Check if window should be managed"""
        if not window:
            return False
        wm_class = window.get_window_type()
        # Skip desktop and dock windows
        if wm_class and wm_class.lower() in ['desktop', 'dock', 'panel']:
            return False
        return True

    def get_relevant_windows(self, workspace=None) -> List[WaylandWindow]:
        """Get list of relevant windows on workspace"""
        windows = self.get_windows()
        return [w for w in windows if self.is_relevant(w)]

    def get_workspace(self, window=None, direction=None, wrap_around=True):
        """Get workspace - simplified for Wayland"""
        # Wayland workspace handling is compositor-specific
        # This is a basic implementation
        return None

    @property
    def screen(self):
        """Compatibility property"""
        return self

    def get_active_workspace(self):
        """Get current workspace"""
        return None

    def get_windows_stacked(self):
        """Get windows in stacking order"""
        return self.get_windows()

    def force_update(self):
        """Compatibility method - refresh window list"""
        pass

    def toggle_showing_desktop(self, show: bool):
        """Toggle showing desktop"""
        logging.warning("toggle_showing_desktop not fully implemented")

    def get_showing_desktop(self) -> bool:
        """Check if showing desktop"""
        return False


def is_wayland() -> bool:
    """Check if running under Wayland"""
    session_type = os.environ.get('XDG_SESSION_TYPE', '').lower()
    wayland_display = os.environ.get('WAYLAND_DISPLAY', '')
    return session_type == 'wayland' or bool(wayland_display)
