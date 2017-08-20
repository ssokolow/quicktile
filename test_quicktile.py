#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Unit Test Suite for QuickTile using Nose test discovery"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

try:
    import pygtk
    pygtk.require('2.0')
except ImportError:
    # Apparently Travis-CI's build environment doesn't add this
    import subprocess, sys
    print("Import Path: {}".format(sys.path))
    subprocess.call(['find', '/usr/lib/python2.7/', '-path', '*gtk*'])

import logging, operator, sys

import gtk
import gtk.gdk, wnck  # pylint: disable=import-error

from quicktile import commands, wm
from quicktile.util import powerset, EnumSafeDict, XInitError

# Ensure code coverage is accurate
from quicktile import __main__  # pylint: disable=unused-import

# Silence flake8 since PyLint already took the line comment spot
__main__  # pylint: disable=pointless-statement

log = logging.getLogger(__name__)

if sys.version_info[0] == 2 and sys.version_info[1] < 7:  # pragma: no cover
    import unittest2 as unittest
else:                                                     # pragma: no cover
    import unittest

# pylint: disable=too-few-public-methods

class ComplainingEnum(object):
    """A parent class for classes which should raise C{TypeError} when compared

    (A stricter version of the annoyance I observed in Glib enums.)
    """
    def __init__(self, testcase):
        self.testcase = testcase

    def __cmp__(self, other):
        """Raises an exception if comparing against another type.
        @raises TypeError: C{type(self) != type(other)}
        @returns: C{id(self) == id(other)}
        @rtype: C{bool}
        """
        if type(self) != type(other):  # pylint: disable=unidiomatic-typecheck
            raise TypeError("Should not be comparing heterogeneous enums: "
                    "%s != %s" % (type(self), type(other)))
        else:
            return cmp(id(self), id(other))

class Thing1(ComplainingEnum):
    """See L{ComplainingEnum}"""
class Thing2(ComplainingEnum):
    """See L{ComplainingEnum}"""

class TestCommandRegistry(unittest.TestCase):
    """Tests for the CommandRegistry class"""
    def setUp(self):
        self.registry = commands.CommandRegistry()

    # TODO: Implement tests for CommandRegistry

# TODO: Implement tests for cycle_dimensions
# TODO: Implement tests for cycle_monitors
# TODO: Implement tests for move_to_position
# TODO: Implement tests for toggle_decorated
# TODO: Implement tests for toggle_desktop
# TODO: Implement tests for toggle_state
# TODO: Implement tests for trigger_keyboard_action
# TODO: Implement tests for workspace_go
# TODO: Implement tests for workspace_send_window

class TestEnumSafeDict(unittest.TestCase):
    """Tests to ensure EnumSafeDict never compares enums of different types"""
    def setUp(self):
        self.thing1 = Thing1(self)
        self.thing2 = Thing2(self)

        self.test_mappings = [
            (self.thing1, 'a'),
            (self.thing2, 'b'),
            (1, self.thing1),
            (2, self.thing2)
        ]

        self.empty = EnumSafeDict()
        self.full = EnumSafeDict(
                *[dict([x]) for x in self.test_mappings])

    def test_testing_shims(self):
        """EnumSafeDict: Testing shims function correctly"""
        for oper in ('lt', 'le', 'eq', 'ne', 'ge', 'gt'):
            with self.assertRaises(TypeError):
                print "Testing %s..." % oper
                getattr(operator, oper)(self.thing1, self.thing2)

    def test_init_with_content(self):
        """EnumSafeDict: Initialization with content"""

        test_map = self.test_mappings[:]

        while test_map:
            key, val = test_map.pop()
            self.assertEqual(self.full[key], val,
                "All things in the input must make it into EnumSafeDict: " +
                 str(key))

        self.assertFalse(test_map, "EnumSafeDict must contain ONLY things from"
                " the input.")

    def test_get_set_del(self):
        """EnumSafeDict: get/set/delitem"""

        # Test the "no matching key" branch of __getitem__
        with self.assertRaises(KeyError):
            self.empty['nonexist']  # pylint: disable=pointless-statement

        # Let Thing1 and Thing2 error out if they're compared in __setitem__
        for key, val in self.test_mappings:
            self.empty[key] = val

        # Test the "matching key" branch of __getitem__ and __delitem__
        for key, val in self.test_mappings:
            assert self.empty[key] == val
            del self.empty[key]
            with self.assertRaises(KeyError):
                self.empty[key]  # pylint: disable=pointless-statement

    # TODO: Complete set of tests which try to trick EnumSafeDict into
    #       comparing thing1 and thing2.


# TODO: Implement tests for GravityLayout

# TODO: Implement tests for KeyBinder

# TODO: Implement tests for QuickTileApp

class TestHelpers(unittest.TestCase):
    """
    @todo: Switch to pytest to get the assertEqual readout from assert in
           bare functions.
    """
    def test_powerset(self):
        """Test that powerset() behaves as expected"""
        src_set = (1, 2, 3)
        expected = [(), (1,), (2,), (3,), (1, 2), (1, 3), (2, 3), (1, 2, 3)]

        for test_set in (tuple(src_set), list(src_set), set(src_set)):
            result = list(powerset(test_set))

            # Obvious requirements
            self.assertIn(tuple(), result)
            self.assertIn(tuple(test_set), result)

            # Check that only subsets are returned
            for subset in expected:
                for item in subset:
                    self.assertIn(item, test_set)

            # Check that ALL subsets are returned
            # FIXME: This shouldn't enforce an ordering constraint.
            self.assertEqual(list(powerset([1, 2, 3])), expected)

    # TODO: Test fmt_table

    # TODO: Test _make_positions

    def test_xiniterror_str(self):
        """XInitError.__str__ output contains provided text"""
        self.assertIn("Testing 123", XInitError("Testing 123"))

class TestWindowManagerDetached(unittest.TestCase):
    """Tests which exercise L{wm.WindowManager} without needing X11."""

    def setUp(self):
        # Shorthand
        self.WM = wm.WindowManager  # pylint: disable=invalid-name

        # Set up a nice, oddly-shaped fake desktop made from screens
        # I actually have access to (though not all on the same PC)
        self.screens = [
                gtk.gdk.Rectangle(0, 0, 1280, 1024),
                gtk.gdk.Rectangle(1280, 0, 1280, 1024),
                gtk.gdk.Rectangle(0, 1024, 1680, 1050),
                gtk.gdk.Rectangle(1680, 1024, 1440, 900)
        ]

        # TODO: Also work in some fake panel struts
        self.desktop = gtk.gdk.Region()
        for rect in self.screens:
            self.desktop.union_with_rect(rect)

    def test_gravity_equivalence(self):
        """Gravity Lookup Table: GDK and WNCK constants are equivalent"""
        for alignment in ('CENTER', 'NORTH', 'NORTH_WEST', 'SOUTH_EAST',
                          'EAST', 'NORTH_EAST', 'SOUTH', 'SOUTH_WEST', 'WEST'):
            self.assertEqual(
                self.WM.gravities[getattr(wnck, 'WINDOW_GRAVITY_{}'.format(
                    alignment.replace('_', '')))],
                self.WM.gravities[getattr(gtk.gdk, 'GRAVITY_{}'.format(
                    alignment))])

    def test_gravity_correctness(self):
        """Gravity Lookup Table: Constants have correct percentage values"""
        for alignment, coords in (
                ('NORTH_WEST', (0, 0)), ('NORTH', (0.5, 0)),
                ('NORTH_EAST', (1.0, 0.0)), ('WEST', (0.0, 0.5)),
                ('CENTER', (0.5, 0.5)), ('EAST', (1, 0.5)),
                ('SOUTH_WEST', (0.0, 1.0)), ('SOUTH', (0.5, 1.0)),
                ('SOUTH_EAST', (1.0, 1.0))):
            self.assertEqual(self.WM.gravities[
                getattr(gtk.gdk, 'GRAVITY_%s' % alignment)], coords)

    def test_win_gravity_noop(self):
        """WindowManager.calc_win_gravity: north-west should be a no-op

        (Might as well use the screen shapes to test this. It saves effort.)
        """
        for rect in [self.desktop.get_clipbox()] + self.screens:
            self.assertEqual((rect.x, rect.y),
                self.WM.calc_win_gravity(rect, gtk.gdk.GRAVITY_NORTH_WEST),
                "NORTHWEST gravity should be a no-op.")

    def test_win_gravity_results(self):
        """WindowManager.calc_win_gravity: proper results"""
        for edge in (100, 200):
            ehalf = edge / 2
            for gravity, expect in (
                    ('NORTH_WEST', (0, 0)), ('NORTH', (-ehalf, 0)),
                    ('NORTH_EAST', (-edge, 0)), ('WEST', (0, -ehalf)),
                    ('CENTER', (-ehalf, -ehalf)), ('EAST', (-edge, -ehalf)),
                    ('SOUTH_WEST', (0, -edge)), ('SOUTH', (-ehalf, -edge)),
                    ('SOUTH_EAST', (-edge, -edge))):
                rect = gtk.gdk.Rectangle(0, 0, edge, edge)
                grav = getattr(gtk.gdk, 'GRAVITY_%s' % gravity)

                self.assertEqual(self.WM.calc_win_gravity(rect, grav), expect)

    # TODO: Test the rest of the functionality

# vim: set sw=4 sts=4 expandtab :
