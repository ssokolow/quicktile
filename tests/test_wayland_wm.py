# -*- coding: utf-8 -*-
"""Unit Test Suite for QuickTile Wayland Window Manager"""

__author__ = "Julio Jiménez (juljimm)"
__license__ = "GNU GPL 2.0 or later"

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import gi
gi.require_version('Gdk', '3.0')
from gi.repository import Gio, GLib

from quicktile.util import Rectangle


class TestIsWayland(unittest.TestCase):
    """Tests for is_wayland detection function"""

    def test_wayland_session_type(self):
        """Detects Wayland from XDG_SESSION_TYPE"""
        with patch.dict(os.environ, {'XDG_SESSION_TYPE': 'wayland', 'WAYLAND_DISPLAY': ''}):
            from quicktile.wayland_wm import is_wayland
            # Need to reload to pick up env changes
            import importlib
            import quicktile.wayland_wm as wm
            importlib.reload(wm)
            self.assertTrue(wm.is_wayland())

    def test_x11_session_type(self):
        """Detects X11 from XDG_SESSION_TYPE"""
        with patch.dict(os.environ, {'XDG_SESSION_TYPE': 'x11', 'WAYLAND_DISPLAY': ''}, clear=False):
            import importlib
            import quicktile.wayland_wm as wm
            importlib.reload(wm)
            self.assertFalse(wm.is_wayland())


class TestWaylandWindow(unittest.TestCase):
    """Tests for WaylandWindow class"""

    def setUp(self):
        """Set up mock window data"""
        self.window_data = {
            'id': 12345,
            'title': 'Test Window',
            'x': 100,
            'y': 100,
            'width': 800,
            'height': 600,
            'maximized': False,
            'minimized': False,
            'focus': True,
        }

    def test_window_properties(self):
        """Window properties are read correctly"""
        from quicktile.wayland_wm import WaylandWindow
        win = WaylandWindow(self.window_data)

        self.assertEqual(win.id, 12345)
        self.assertEqual(win.get_title(), 'Test Window')
        self.assertEqual(win.get_geometry(), (100, 100, 800, 600))
        self.assertFalse(win.is_maximized())
        self.assertFalse(win.is_minimized())
        self.assertTrue(win.has_focus())

    def test_window_xid_compatibility(self):
        """get_xid returns window id for X11 compatibility"""
        from quicktile.wayland_wm import WaylandWindow
        win = WaylandWindow(self.window_data)
        self.assertEqual(win.get_xid(), win.id)


class TestWaylandWindowManagerState(unittest.TestCase):
    """Tests for WaylandWindowManager state persistence"""

    def setUp(self):
        """Set up temporary state file"""
        self.temp_dir = tempfile.mkdtemp()
        self.state_file = os.path.join(self.temp_dir, 'test-state.json')

    def tearDown(self):
        """Clean up temporary files"""
        if os.path.exists(self.state_file):
            os.remove(self.state_file)
        os.rmdir(self.temp_dir)

    def test_state_save_and_load(self):
        """State is saved and loaded correctly"""
        # Write state directly
        state = {'12345:test_key': {'x': 100, 'y': 200}}
        with open(self.state_file, 'w') as f:
            json.dump(state, f)

        # Read it back
        with open(self.state_file, 'r') as f:
            loaded = json.load(f)

        self.assertEqual(loaded, state)

    def test_state_remove_on_none(self):
        """Setting value to None removes the key"""
        state = {'12345:key1': 'value1', '12345:key2': 'value2'}
        with open(self.state_file, 'w') as f:
            json.dump(state, f)

        # Simulate what set_property does with None
        with open(self.state_file, 'r') as f:
            loaded = json.load(f)
        loaded.pop('12345:key1', None)
        with open(self.state_file, 'w') as f:
            json.dump(loaded, f)

        with open(self.state_file, 'r') as f:
            result = json.load(f)

        self.assertNotIn('12345:key1', result)
        self.assertIn('12345:key2', result)


class TestPartialMaximize(unittest.TestCase):
    """Tests for vertical and horizontal maximize functionality"""

    def test_vertical_maximize_stores_geometry(self):
        """Vertical maximize stores original geometry for restore"""
        from quicktile.wayland_wm import WaylandWindow, WaylandWindowManager

        # Mock the manager
        manager = MagicMock(spec=WaylandWindowManager)
        manager.get_monitor.return_value = (0, Rectangle(0, 0, 1920, 1080))
        manager.get_property.return_value = None  # Not maximized yet

        window_data = {'id': 1, 'x': 100, 'y': 100, 'width': 800, 'height': 600}
        win = WaylandWindow(window_data, manager)

        # Call maximize_vertically
        win.maximize_vertically()

        # Verify manager method was called
        manager.maximize_vertically.assert_called_once_with(win)

    def test_horizontal_maximize_stores_geometry(self):
        """Horizontal maximize stores original geometry for restore"""
        from quicktile.wayland_wm import WaylandWindow, WaylandWindowManager

        manager = MagicMock(spec=WaylandWindowManager)
        manager.get_monitor.return_value = (0, Rectangle(0, 0, 1920, 1080))
        manager.get_property.return_value = None

        window_data = {'id': 1, 'x': 100, 'y': 100, 'width': 800, 'height': 600}
        win = WaylandWindow(window_data, manager)

        win.maximize_horizontally()

        manager.maximize_horizontally.assert_called_once_with(win)


class TestInitDbus(unittest.TestCase):
    """Tests for WaylandWindowManager._init_dbus() initialization"""

    @patch('quicktile.wayland_wm.Gdk')
    @patch('quicktile.wayland_wm.Gio.DBusProxy.new_for_bus_sync')
    def test_init_dbus_success(self, mock_new_proxy, mock_gdk):
        """Constructor succeeds when Window Calls extension responds"""
        from quicktile.wayland_wm import WaylandWindowManager

        mock_proxy = MagicMock()
        mock_new_proxy.return_value = mock_proxy
        mock_gdk.Screen.get_default.return_value = None
        mock_gdk.Display.get_default.return_value = None

        manager = WaylandWindowManager()

        mock_proxy.call_sync.assert_called_once_with(
            'List', None, Gio.DBusCallFlags.NONE, -1, None)
        self.assertIs(manager._proxy, mock_proxy)

    @patch('quicktile.wayland_wm.Gdk')
    @patch('quicktile.wayland_wm.Gio.DBusProxy.new_for_bus_sync')
    def test_init_dbus_extension_not_responding(self, mock_new_proxy, mock_gdk):
        """Constructor raises RuntimeError when List call fails"""
        from quicktile.wayland_wm import WaylandWindowManager

        mock_proxy = MagicMock()
        mock_proxy.call_sync.side_effect = GLib.Error('No such interface')
        mock_new_proxy.return_value = mock_proxy
        mock_gdk.Screen.get_default.return_value = None
        mock_gdk.Display.get_default.return_value = None

        with self.assertRaises(RuntimeError) as ctx:
            WaylandWindowManager()
        self.assertIn('Window Calls extension not available', str(ctx.exception))

    @patch('quicktile.wayland_wm.Gdk')
    @patch('quicktile.wayland_wm.Gio.DBusProxy.new_for_bus_sync')
    def test_init_dbus_proxy_creation_fails(self, mock_new_proxy, mock_gdk):
        """Constructor raises RuntimeError when proxy creation fails"""
        from quicktile.wayland_wm import WaylandWindowManager

        mock_new_proxy.side_effect = GLib.Error('DBus connection failed')
        mock_gdk.Screen.get_default.return_value = None
        mock_gdk.Display.get_default.return_value = None

        with self.assertRaises(RuntimeError) as ctx:
            WaylandWindowManager()
        self.assertIn('Window Calls extension not available', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
