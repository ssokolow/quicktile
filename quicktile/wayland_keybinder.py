"""Wayland keybinder using GNOME Shell's GrabAccelerator D-Bus API"""

__author__ = "QuickTile Wayland Adaptation"
__license__ = "GNU GPL 2.0 or later"

import logging
from typing import Callable, Dict, Optional

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gio, GLib, Gtk, Gdk


class WaylandKeyBinder:
    """Keybinder for Wayland using GNOME Shell's D-Bus API"""

    DBUS_NAME = "org.gnome.Shell"
    DBUS_PATH = "/org/gnome/Shell"
    DBUS_INTERFACE = "org.gnome.Shell"

    # Mode flags for GrabAccelerator
    MODE_NONE = 0
    MODE_OVERRIDE_SYSTEM_SHORTCUTS = 1

    # Grab flags
    GRAB_NONE = 0

    def __init__(self):
        self._bindings: Dict[int, Callable] = {}  # action_id -> callback
        self._accel_map: Dict[str, int] = {}  # accelerator -> action_id
        self._proxy: Optional[Gio.DBusProxy] = None
        self._init_dbus()

    def _init_dbus(self):
        """Initialize D-Bus connection to GNOME Shell"""
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

            # Connect to AcceleratorActivated signal
            self._proxy.connect('g-signal', self._on_signal)
            logging.info("Connected to GNOME Shell for key binding")

        except GLib.Error as e:
            logging.error("Failed to connect to GNOME Shell: %s", e)
            raise RuntimeError(
                "Could not connect to GNOME Shell D-Bus interface. "
                "Make sure you are running GNOME Shell."
            )

    def _on_signal(self, proxy, sender_name, signal_name, parameters):
        """Handle D-Bus signals from GNOME Shell"""
        if signal_name == 'AcceleratorActivated':
            action_id, params = parameters.unpack()
            logging.debug("Accelerator activated: action_id=%d", action_id)

            if action_id in self._bindings:
                try:
                    self._bindings[action_id]()
                except Exception as e:
                    logging.error("Error in keybinding callback: %s", e)

    def bind(self, accel: str, callback: Callable[[], None]) -> bool:
        """Bind a global key combination to a callback.

        :param accel: Accelerator string (e.g., '<Ctrl><Alt>Left')
        :param callback: Function to call when key is pressed
        :returns: True if binding was successful
        """
        # Normalize accelerator format for GNOME Shell
        normalized = self._normalize_accel(accel)

        if not normalized:
            logging.warning("Failed to parse accelerator: %s", accel)
            return False

        try:
            result = self._proxy.call_sync(
                'GrabAccelerator',
                GLib.Variant('(suu)', (normalized, self.MODE_NONE, self.GRAB_NONE)),
                Gio.DBusCallFlags.NONE,
                -1,
                None
            )

            action_id = result.unpack()[0]

            if action_id == 0:
                logging.warning("Failed to grab accelerator: %s", accel)
                return False

            self._bindings[action_id] = callback
            self._accel_map[accel] = action_id
            logging.debug("Bound accelerator %s -> action_id %d", accel, action_id)
            return True

        except GLib.Error as e:
            logging.error("Failed to grab accelerator %s: %s", accel, e)
            return False

    def unbind(self, accel: str) -> bool:
        """Unbind a previously bound accelerator.

        :param accel: Accelerator string to unbind
        :returns: True if unbinding was successful
        """
        if accel not in self._accel_map:
            return False

        action_id = self._accel_map[accel]

        try:
            result = self._proxy.call_sync(
                'UngrabAccelerator',
                GLib.Variant('(u)', (action_id,)),
                Gio.DBusCallFlags.NONE,
                -1,
                None
            )

            success = result.unpack()[0]

            if success:
                del self._bindings[action_id]
                del self._accel_map[accel]
                logging.debug("Unbound accelerator %s", accel)

            return success

        except GLib.Error as e:
            logging.error("Failed to ungrab accelerator %s: %s", accel, e)
            return False

    def unbind_all(self):
        """Unbind all registered accelerators"""
        action_ids = list(self._bindings.keys())

        if not action_ids:
            return

        try:
            result = self._proxy.call_sync(
                'UngrabAccelerators',
                GLib.Variant('(au)', (action_ids,)),
                Gio.DBusCallFlags.NONE,
                -1,
                None
            )
            logging.debug("Unbound all accelerators")
        except GLib.Error as e:
            logging.error("Failed to ungrab accelerators: %s", e)

        self._bindings.clear()
        self._accel_map.clear()

    def _normalize_accel(self, accel: str) -> Optional[str]:
        """Normalize accelerator string for GNOME Shell.

        Converts GTK-style accelerators to GNOME Shell format.
        """
        # Parse with GTK
        key, mods = Gtk.accelerator_parse(accel)

        if key == 0:
            return None

        # Get key name
        keyname = Gdk.keyval_name(key)
        if not keyname:
            return None

        # Build GNOME Shell format accelerator
        parts = []

        if mods & Gdk.ModifierType.CONTROL_MASK:
            parts.append('<Control>')
        if mods & Gdk.ModifierType.MOD1_MASK:  # Alt
            parts.append('<Alt>')
        if mods & Gdk.ModifierType.SHIFT_MASK:
            parts.append('<Shift>')
        if mods & Gdk.ModifierType.SUPER_MASK:
            parts.append('<Super>')

        parts.append(keyname)

        return ''.join(parts)

    @staticmethod
    def parse_accel(accel: str):
        """Parse accelerator string and return (keyval, modmask)"""
        return Gtk.accelerator_parse(accel)


def init_wayland_keybinder() -> WaylandKeyBinder:
    """Initialize and return a Wayland keybinder instance"""
    return WaylandKeyBinder()
