#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit Test Suite for QuickTile using Nose test discovery"""

from __future__ import print_function

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

# TODO: I need a functional test to make sure issue #25 doesn't regress

import logging, operator, sys

import gi
gi.require_version('cairo', '1.0')
gi.require_version('Gdk', '3.0')
gi.require_version('Gtk', '3.0')
gi.require_version('Wnck', '3.0')
from gi.repository import Gdk, Wnck  # pylint: disable=E0611

from quicktile import commands, wm
from quicktile.util import (powerset, EnumSafeDict, Rectangle, Region,
                            XInitError)

# Ensure code coverage is accurate
from quicktile import __main__  # pylint: disable=unused-import

# Silence flake8 since PyLint already took the line comment spot
__main__  # pylint: disable=pointless-statement

log = logging.getLogger(__name__)

if sys.version_info[0] == 2 and sys.version_info[1] < 7:  # pragma: no cover
    import unittest2 as unittest
else:                                                     # pragma: no cover
    import unittest

# Set up a nice, oddly-shaped fake desktop made from screens
# I actually have access to (though not all on the same PC)
MOCK_SCREENS = [
    Rectangle(0, 0, 1280, 1024),
    Rectangle(1280, 0, 1280, 1024),
    Rectangle(0, 1024, 1680, 1050),
    Rectangle(1680, 1024, 1440, 900)
]

# pylint: disable=too-few-public-methods


class ComplainingEnum(object):
    """A parent class for classes which should raise C{TypeError} when compared

    (A stricter version of the annoyance I observed in Glib enums.)
    """
    def __init__(self, testcase):  # type: (unittest.TestCase) -> None
        self.testcase = testcase
        # TODO: Why did I store this value again?

    def __cmp__(self, other):  # type: (ComplainingEnum) -> int
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
    def setUp(self):  # type: () -> None
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
    def setUp(self):  # type: () -> None
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

    def test_testing_shims(self):  # type: () -> None
        """EnumSafeDict: Testing shims function correctly"""
        for oper in ('lt', 'le', 'eq', 'ne', 'ge', 'gt'):
            with self.assertRaises(TypeError):
                print("Testing %s..." % oper)
                getattr(operator, oper)(self.thing1, self.thing2)

    def test_init_with_content(self):  # type: () -> None
        """EnumSafeDict: Initialization with content"""

        test_map = self.test_mappings[:]

        while test_map:
            key, val = test_map.pop()
            self.assertEqual(self.full[key], val,
                "All things in the input must make it into EnumSafeDict: " +
                 str(key))

        self.assertFalse(test_map, "EnumSafeDict must contain ONLY things from"
                " the input.")

    def test_get_set_del(self):  # type: () -> None
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
    def test_powerset(self):  # type: () -> None
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

    def test_xiniterror_str(self):  # type: () -> None
        """XInitError.__str__ output contains provided text"""
        self.assertIn("Testing 123", str(XInitError("Testing 123")))


class TestWindowGravity(unittest.TestCase):
    """Test the equivalence and correctness of L{wm.GRAVITY} values."""

    def setUp(self):  # type: () -> None
        # Set up a nice, oddly-shaped fake desktop made from screens
        # I actually have access to (though not all on the same PC)

        # TODO: Also work in some fake panel struts
        self.desktop = Region()
        for rect in MOCK_SCREENS:
            self.desktop.union_with_rect(rect)

    def test_gravity_equivalence(self):  # type: () -> None
        """Gravity Lookup Table: text/GDK/WNCK constants are equivalent"""
        for alignment in ('CENTER', 'NORTH', 'NORTH_WEST', 'SOUTH_EAST',
                          'EAST', 'NORTH_EAST', 'SOUTH', 'SOUTH_WEST', 'WEST'):
            self.assertEqual(wm.GRAVITY[alignment],
                wm.GRAVITY[getattr(Gdk.Gravity, alignment)])
            self.assertEqual(
                wm.GRAVITY[getattr(Wnck.WindowGravity,
                                   alignment.replace('_', ''))],
                wm.GRAVITY[getattr(Gdk.Gravity, alignment)])

    def test_gravity_correctness(self):  # type: () -> None
        """Gravity Lookup Table: Constants have correct percentage values"""
        for alignment, coords in (
                ('NORTH_WEST', (0, 0)), ('NORTH', (0.5, 0)),
                ('NORTH_EAST', (1.0, 0.0)), ('WEST', (0.0, 0.5)),
                ('CENTER', (0.5, 0.5)), ('EAST', (1, 0.5)),
                ('SOUTH_WEST', (0.0, 1.0)), ('SOUTH', (0.5, 1.0)),
                ('SOUTH_EAST', (1.0, 1.0))):
            self.assertEqual(wm.GRAVITY[
                getattr(Gdk.Gravity, alignment)], coords)


class TestWindowManagerDetached(unittest.TestCase):
    """Tests which exercise L{wm.WindowManager} without needing X11."""

    def setUp(self):  # type: () -> None
        # Shorthand
        self.WM = wm.WindowManager  # pylint: disable=invalid-name

        # TODO: Also work in some fake panel struts
        self.desktop = Region()
        for rect in MOCK_SCREENS:
            self.desktop.union_with_rect(rect)

    def test_win_gravity_noop(self):  # type: () -> None
        """WindowManager.calc_win_gravity: north-west should be a no-op

        (Might as well use the screen shapes to test this. It saves effort.)
        """
        for rect in [self.desktop.get_clipbox()] + MOCK_SCREENS:
            self.assertEqual((rect.x, rect.y),
                self.WM.calc_win_gravity(rect, Gdk.Gravity.NORTH_WEST),
                "NORTHWEST gravity should be a no-op.")

    def test_win_gravity_results(self):  # type: () -> None
        """WindowManager.calc_win_gravity: proper results"""
        for edge in (100, 200):
            ehalf = edge / 2
            for gravity, expect in (
                    ('NORTH_WEST', (0, 0)), ('NORTH', (-ehalf, 0)),
                    ('NORTH_EAST', (-edge, 0)), ('WEST', (0, -ehalf)),
                    ('CENTER', (-ehalf, -ehalf)), ('EAST', (-edge, -ehalf)),
                    ('SOUTH_WEST', (0, -edge)), ('SOUTH', (-ehalf, -edge)),
                    ('SOUTH_EAST', (-edge, -edge))):
                rect = Rectangle(0, 0, edge, edge)
                grav = getattr(Gdk.Gravity, gravity)

                self.assertEqual(self.WM.calc_win_gravity(rect, grav), expect)

    # TODO: Test the rest of the functionality

# vim: set sw=4 sts=4 expandtab :
