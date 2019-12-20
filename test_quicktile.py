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
from quicktile.util import (clamp_idx, powerset, EnumSafeDict, Rectangle,
                            Region, XInitError)

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
    def __hash__(self):
        """Use the identity of the object for its hash"""
        return id(self)

    def __eq__(self, other):
        """Raises an exception if comparing against another type.
        @raises TypeError: C{type(self) != type(other)}
        @returns: C{id(self) == id(other)}
        @rtype: C{bool}
        """
        if not isinstance(self, type(other)):
            raise TypeError("Should not be comparing heterogeneous enums: "
                    "%s != %s" % (type(self), type(other)))
        else:
            return id(self) == id(other)


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

# TODO: Move tests for util.py into tests/util.py


class TestEnumSafeDict(unittest.TestCase):
    """Tests to ensure EnumSafeDict never compares enums of different types"""
    def setUp(self):  # type: () -> None
        self.thing1 = Thing1()
        self.thing2 = Thing2()

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

        # Test the "no matching key" branch of __delitem__
        with self.assertRaises(KeyError):
            del self.empty['nonexist']

        # Let Thing1 and Thing2 error out if they're compared in __setitem__
        for key, val in self.test_mappings:
            self.empty[key] = val

        # Test the "matching key" branch of __getitem__ and __delitem__
        for key, val in self.test_mappings:
            assert self.empty[key] == val
            del self.empty[key]
            with self.assertRaises(KeyError):
                self.empty[key]  # pylint: disable=pointless-statement

    def test_iteritems(self):
        """EnumSafeDict: iteritems"""
        tests = dict(self.test_mappings)
        items = dict(self.full.iteritems())

        # Workaround to dodge the "can't check unlike types for equality"
        # (which is normally desired) in this one instance
        for key, val in tests.items():
            self.assertEqual(items[key], val)
        for key, val in items.items():
            self.assertEqual(tests[key], val)

    def test_keys(self):
        """EnumSafeDict: keys"""
        keys = self.full.keys()
        tests = dict(self.test_mappings)

        for key in keys:
            tests[key]  # pylint: disable=pointless-statement
        for key in tests.keys():
            self.assertIn(key, keys)

    def test_repr(self):  # type: () -> None
        """EnumSafeDict: Test basic repr() function"""
        # Can't use self.full because it contains memory addresses and dicts
        # don't have a deterministic order
        stably_named = EnumSafeDict({'a': 1})

        self.assertEqual(repr(self.empty), "EnumSafeDict()")
        self.assertEqual(repr(stably_named), "EnumSafeDict({'a': 1})")

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

    def test_clamp_idx_default(self):
        """Test that clamp_idx defaults to wrapping behaviour"""
        for x in range(-5, 15):
            self.assertEqual(clamp_idx(x, 10), clamp_idx(x, 10, wrap=True))

    def test_clamp_idx_wrap(self):  # type: () -> None
        """Test that clamp_idx(wrap=True) wraps as expected"""
        self.assertEqual(clamp_idx(5, 10, wrap=True), 5)
        self.assertEqual(clamp_idx(-1, 10, wrap=True), 9)
        self.assertEqual(clamp_idx(11, 10, wrap=True), 1)
        self.assertEqual(clamp_idx(15, 10, wrap=True), 5)

    def test_clamp_idx(self):  # type: () -> None
        """Test that clamp_idx(wrap=False) saturates as expected"""
        self.assertEqual(clamp_idx(5, 10, wrap=False), 5)
        self.assertEqual(clamp_idx(-1, 10, wrap=False), 0)
        self.assertEqual(clamp_idx(11, 10, wrap=False), 9)
        self.assertEqual(clamp_idx(15, 10, wrap=False), 9)

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


class TestRectangle(unittest.TestCase):
    """Tests for my custom Rectangle class"""

    def setUp(self):
        """Implicitly test positional and keyword construction during setup"""
        self.rect1 = Rectangle(1, 2, 3, 4)
        self.rect2 = Rectangle(x=2, y=3, width=4, height=5)
        self.rect3 = Rectangle(-1, -2, x2=3, y2=4)

    def test_none_safe(self):
        """Rectangle: __new__ doesn't attempt to compare None and int"""
        Rectangle(0, 0, width=None, height=None, x2=0, y2=0)

    def test_member_access(self):
        """Rectangle: quacks like a namedtuple"""
        self.assertEqual(self.rect1[0], 1)
        self.assertEqual(self.rect1.y, 2)
        self.assertEqual(self.rect1, (1, 2, 3, 4))

    def test_negative_size(self):
        """Rectangle: test normalization of negative sizes"""
        self.assertEqual(Rectangle(3, 2, -2, 2), (1, 2, 2, 2))
        self.assertEqual(Rectangle(1, 4, 2, -2), (1, 2, 2, 2))
        self.assertEqual(Rectangle(3, 4, -2, -2), (1, 2, 2, 2))

    def test_twopoint_construction(self):
        """Rectangle: test construction using two-point form"""
        # Regular
        self.assertEqual(Rectangle(1, 2, x2=3, y2=4), (1, 2, 2, 2))

        # Origin-crossing
        self.assertEqual(self.rect3, (-1, -2, 4, 6))

        # Negative width and/or height
        self.assertEqual(Rectangle(3, 2, x2=1, y2=4), (1, 2, 2, 2))
        self.assertEqual(Rectangle(1, 4, x2=3, y2=2), (1, 2, 2, 2))
        self.assertEqual(Rectangle(3, 4, x2=1, y2=2), (1, 2, 2, 2))

        self.assertEqual(Rectangle(-3, -4, x2=-1, y2=-2), (-3, -4, 2, 2))
        self.assertEqual(Rectangle(-3, -4, x2=-1, y2=-2), (-3, -4, 2, 2))
        self.assertEqual(Rectangle(-3, -4, x2=-1, y2=-2), (-3, -4, 2, 2))

        self.assertEqual(Rectangle(3, 4, x2=-1, y2=-2), (-1, -2, 4, 6))
        self.assertEqual(Rectangle(-1, 4, x2=3, y2=-2), (-1, -2, 4, 6))
        self.assertEqual(Rectangle(3, -2, x2=-1, y2=4), (-1, -2, 4, 6))

        # Bad argument combinations
        with self.assertRaises(ValueError):
            Rectangle(1, 2, 3, 4, 5)
        with self.assertRaises(ValueError):
            Rectangle(1, 2, 3, 4, 5, 6)
        with self.assertRaises(ValueError):
            Rectangle(x=1, y=2, width=3, height=4, x2=5)
        with self.assertRaises(ValueError):
            Rectangle(x=1, y=2, width=3, height=4, y2=6)

    def test_and(self):
        """Rectangle: bitwise & performs intersection correctly"""
        self.assertEqual(self.rect1 & self.rect2, Rectangle(2, 3, 2, 3))
        self.assertEqual(self.rect2 & self.rect1, Rectangle(2, 3, 2, 3))

        # Basic test that unrecognized types fail properly
        with self.assertRaises(TypeError):
            print(self.rect1 & 5)

    def test_bool(self):
        """Rectangle: only truthy if area is nonzero"""
        self.assertTrue(self.rect1)
        self.assertTrue(self.rect2)
        self.assertTrue(Rectangle(-1, -2, 1, 1))  # Negative
        self.assertTrue(Rectangle(-1, -2, 5, 5))  # Origin-crossing
        self.assertTrue(Rectangle(0, 0, 5, 5))  # (0, 0) start
        self.assertFalse(Rectangle(0, 0, 0, 0))
        self.assertFalse(Rectangle(1, 2, 0, 0))
        self.assertFalse(Rectangle(1, 2, 1, 0))
        self.assertFalse(Rectangle(1, 2, 0, 1))
        self.assertFalse(Rectangle(-1, -2, 0, 0))
        self.assertFalse(Rectangle(-1, -2, 1, 0))
        self.assertFalse(Rectangle(-1, -2, 0, 1))

    def test_or(self):
        """Rectangle: bitwise | finds bounding box for two rectangles"""
        self.assertEqual(self.rect1 | self.rect2, Rectangle(
            self.rect1.x, self.rect1.y,
            self.rect2.x2 - self.rect1.x,
            self.rect2.y2 - self.rect1.y))
        self.assertEqual(self.rect2 | self.rect1, Rectangle(
            self.rect1.x, self.rect1.y,
            self.rect2.x2 - self.rect1.x,
            self.rect2.y2 - self.rect1.y))
        self.assertEqual(Rectangle(-2, -5, 1, 1) | Rectangle(2, 5, 1, 1),
                         Rectangle(-2, -5, x2=3, y2=6))

        # Basic test that unrecognized types fail properly
        with self.assertRaises(TypeError):
            print(self.rect1 | 5)

    def test_two_point_form(self):
        """Rectangle: two-point-form properties function properly"""
        self.assertEqual(self.rect1.x2, self.rect1.x + self.rect1.width)
        self.assertEqual(self.rect1.y2, self.rect1.y + self.rect1.height)


class TestRegion(unittest.TestCase):
    """Tests for my custom Region class"""

    def _check_copy(self, region1, region2):
        """Helper for checking for a deep copy"""
        self.assertEqual(region1, region2)
        self.assertIsNot(region1, region2)

        for rect1, rect2 in zip(region1._rects, region2._rects):
            self.assertEqual(rect1, rect2)
            self.assertIsNot(rect1, rect2)

    # TODO: Test __and__

    def test_bool(self):
        """Region: __bool__"""
        # Empty regions are falsy
        test_region = Region()
        self.assertFalse(test_region)

        # Force a denormalized region to verify that empty rectangles are still
        # treated as falsy
        test_region._rects.append(Rectangle(0, 0, 0, 0))
        self.assertFalse(test_region)

        # Regions containing at least one empty rectangle are truthy
        self.assertTrue(Region(Rectangle(0, 0, 0, 0), Rectangle(0, 0, 1, 1)))

    def test_construction(self):
        """Region: copy"""
        test_rects = [Rectangle(1, 2, 3, 4), Rectangle(5, 6, 7, 8)]
        test_region_1 = Region(*test_rects)
        test_region_2 = Region(*test_rects)

        self._check_copy(test_region_1, test_region_2)

    def test_copy(self):
        """Region: copy"""
        test_region_1 = Region(Rectangle(1, 2, 3, 4))
        test_region_2 = test_region_1.copy()

        self._check_copy(test_region_1, test_region_2)

    def test_eq(self):
        """Region: __eq__"""
        test_rect = Rectangle(1, 2, 3, 4)
        test_region_1 = Region(test_rect)
        test_region_2 = test_region_1.copy()

        self.assertEqual(test_region_1, test_region_1)
        self.assertEqual(test_region_1, test_region_2)
        self.assertNotEqual(test_region_1, test_rect)

        test_region_3 = Region(Rectangle(1, 2, 3, 4))
        test_region_4 = Region(Rectangle(1, 2, 3, 5))
        test_region_5 = Region(Rectangle(1, 2, 3, 4), Rectangle(1, 2, 3, 5))
        self.assertEqual(test_region_1, test_region_3)
        self.assertNotEqual(test_region_1, test_region_4)
        self.assertNotEqual(test_region_1, test_region_5)

    def test_get_clipbox(self):
        """Region: get_clipbox"""
        # one rect
        self.assertEqual(Rectangle(0, 0, 2, 1),
            Region(Rectangle(0, 0, 2, 1)).get_clipbox())

        # Top-left and bottom-right (contiguous)
        self.assertEqual(Rectangle(0, 0, 2, 5),
            Region(Rectangle(0, 0, 2, 1), Rectangle(1, 0, 1, 5)).get_clipbox())

        # Top-left and bottom-right (non-contiguous)
        self.assertEqual(Rectangle(0, 0, 6, 6),
            Region(Rectangle(0, 0, 1, 1), Rectangle(5, 5, 1, 1)).get_clipbox())

        # Bottom-left and top-right (non-contiguous)
        self.assertEqual(Rectangle(0, 0, 6, 6),
            Region(Rectangle(0, 5, 1, 1), Rectangle(5, 0, 1, 1)).get_clipbox())

        # Short and tall (non-contiguous)
        self.assertEqual(Rectangle(0, 0, 6, 5),
            Region(Rectangle(0, 3, 1, 1), Rectangle(5, 0, 1, 5)).get_clipbox())

        # Empty rects should be eliminated
        test_region = Region(Rectangle(0, 0, 1, 1), Rectangle(5, 5, 0, 1))
        self.assertEqual(Rectangle(0, 0, 1, 1), test_region.get_clipbox())

        # Force a denormalized region to verify empty rects don't clipbox
        test_region._rects.append(Rectangle(3, 8, 1, 0))
        self.assertEqual(Rectangle(0, 0, 1, 1), test_region.get_clipbox())

    # TODO: Test __ior__

    def test_repr(self):
        """Region: __repr__"""
        self.assertEqual(repr(Region()), "Region()")
        self.assertEqual(repr(Region(Rectangle(0, 0, 0, 0))), "Region()")
        self.assertEqual(
            repr(Region(Rectangle(0, 0, 0, 0), Rectangle(0, 0, 1, 1))),
            "Region(Rectangle(x=0, y=0, width=1, height=1))")
        self.assertIn(
            repr(Region(Rectangle(0, 2, 1, 1), Rectangle(0, 0, 1, 1))), (
                "Region(Rectangle(x=0, y=2, width=1, height=1), "
                "Rectangle(x=0, y=0, width=1, height=1))",
                "Region(Rectangle(x=0, y=0, width=1, height=1), "
                "Rectangle(x=0, y=2, width=1, height=1))"))


class TestWindowGravity(unittest.TestCase):
    """Test the equivalence and correctness of L{wm.GRAVITY} values."""

    def setUp(self):  # type: () -> None
        # Set up a nice, oddly-shaped fake desktop made from screens
        # I actually have access to (though not all on the same PC)

        # TODO: Also work in some fake panel struts
        self.desktop = Region()
        for rect in MOCK_SCREENS:
            self.desktop |= rect

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
            self.desktop |= rect

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
