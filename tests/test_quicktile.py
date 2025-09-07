# -*- coding: utf-8 -*-
"""Unit Test Suite for QuickTile using PyTest test discovery"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

# TODO: I need a functional test to make sure issue #25 doesn't regress

import configparser, logging, os, shutil, tempfile, unittest

# Ensure code coverage counts modules not yet imported by tests.
from quicktile import config, __main__  # NOQA pylint: disable=unused-import

log = logging.getLogger(__name__)

# class TestCommandRegistry(unittest.TestCase):
#     """Tests for the `CommandRegistry` class"""
#     def setUp(self):
#         self.registry = commands.CommandRegistry()
#
#     # TODO: Implement tests for CommandRegistry

# TODO: Implement tests for cycle_dimensions
# TODO: Implement tests for cycle_monitors
# TODO: Implement tests for move_to_position
# TODO: Implement tests for toggle_decorated
# TODO: Implement tests for toggle_desktop
# TODO: Implement tests for toggle_state
# TODO: Implement tests for trigger_keyboard_action
# TODO: Implement tests for workspace_go
# TODO: Implement tests for workspace_send_window

# TODO: Implement tests for KeyBinder

# TODO: Implement tests for QuickTileApp


class ConfigV1Test(unittest.TestCase):
    """Tests for parsing ConfigParser-era quicktile.cfg files"""

    def setUp(self):
        """Set up scratch space for config files at the start of each unit"""
        self.testdir = tempfile.mkdtemp(prefix='quicktile-config-test-')
        self.testpath = os.path.join(self.testdir, 'test.config')

    def tearDown(self):
        """Delete the scratch space when each test is finished"""
        shutil.rmtree(self.testdir)

    def test_creates_on_first_run(self):
        """Config file is created if it doesn't exist"""
        self.assertFalse(os.path.exists(self.testpath))
        parsed = config.load_config(self.testpath)
        self.assertTrue(os.path.exists(self.testpath))

        # Verify all defaults were put in correctly
        for section, lines in config.DEFAULTS.items():
            for key, value in lines.items():
                self.assertEqual(str(value), parsed.get(section, key))

        # Verify nothing but defaults and cfg_schema were put in
        for section in parsed.sections():
            for option in parsed.options(section):
                if option == 'cfg_schema':
                    self.assertEqual(parsed.get(section, option), '1')
                else:
                    self.assertEqual(
                        parsed.get(section, option),
                        str(config.DEFAULTS[section][option]))

    def test_keys_are_case_sensitive(self):
        """Config keys are case-sensitive"""
        parsed = config.load_config(self.testpath)

        self.assertEqual('True', parsed.get('general', 'MovementsWrap'))
        self.assertRaises(configparser.NoSectionError,
            parsed.get, 'General', 'movementswrap')
        self.assertRaises(configparser.NoOptionError,
            parsed.get, 'general', 'movementswrap')

    # TODO: Check schema version

    def test_updating_modkeys_format(self):
        """ModKeys format is updated correctly"""
        with open(self.testpath, 'w') as fobj:
            fobj.write("[general]\ncfg_schema = 1\nModMask = Ctrl Alt")

        parsed = config.load_config(self.testpath)
        self.assertEqual("<Ctrl><Alt>", parsed.get('general', 'ModMask'))

        # Test twice to guard against hard-coded overwrites
        with open(self.testpath, 'w') as fobj:
            fobj.write("[general]\ncfg_schema = 1\nModMask = Ctrl Shift")

        parsed = config.load_config(self.testpath)
        self.assertEqual("<Ctrl><Shift>", parsed.get('general', 'ModMask'))

    def test_loading_keybindgs(self):
        """Keybinds not pulled from DEFAULTS load correctly"""
        # Assert default different than test value
        parsed = config.load_config(self.testpath)
        self.assertEqual("monitor-switch", parsed.get('keys', 'KP_Enter'))

        with open(self.testpath, 'w') as fobj:
            fobj.write("[keys]\nKP_Enter = maximize")

        # Assert test value
        parsed = config.load_config(self.testpath)
        self.assertEqual("maximize", parsed.get('keys', 'KP_Enter'))

    def test_remapping_invalid_keynames(self):
        """Punctuation keybinds get remapped to keysyms"""
        # Assert defaults different than test value
        parsed = config.load_config(self.testpath)
        for name in (',', '.', '+', '-', 'comma', 'period', 'plus', 'minus'):
            self.assertRaises(configparser.NoOptionError,
                parsed.get, 'keys', name)

        with open(self.testpath, 'w') as fobj:
            fobj.write("[keys]\n, = left\n. = right\n+ = top\n- = bottom")

        # Assert test values
        parsed = config.load_config(self.testpath)
        for name in (',', '.', '+', '-'):
            self.assertRaises(configparser.NoOptionError,
                parsed.get, 'keys', name)
        for name, mapping in (
                ('comma', 'left'),
                ('period', 'right'),
                ('plus', 'top'),
                ('minus', 'bottom')):
            self.assertEqual(parsed.get('keys', name), mapping)

        # Verify the changes got committed to disk
        reparsed = config.load_config(self.testpath)
        for name, mapping in (
                ('comma', 'left'),
                ('period', 'right'),
                ('plus', 'top'),
                ('minus', 'bottom')):
            self.assertEqual(reparsed.get('keys', name), mapping)

    def test_remapping_middle(self):
        """'middle' action automatically gets remapped to 'center'"""
        # Assert defaults different than test value
        parsed = config.load_config(self.testpath)
        self.assertEqual("left", parsed.get('keys', 'KP_4'))

        with open(self.testpath, 'w') as fobj:
            fobj.write("[keys]\nKP_4 = middle")

        # Assert test values
        parsed = config.load_config(self.testpath)
        self.assertEqual("center", parsed.get('keys', 'KP_4'))

        # Verify the changes got committed to disk
        with open(self.testpath, 'r') as fobj:
            self.assertTrue('\nKP_4 = center\n' in fobj.read())

# vim: set sw=4 sts=4 expandtab :
