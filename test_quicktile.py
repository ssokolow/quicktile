#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit Test Suite for QuickTile using Nose test discovery"""

from __future__ import print_function

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

# TODO: I need a functional test to make sure issue #25 doesn't regress

import logging, sys

from quicktile import commands
from quicktile.util import (clamp_idx, euclidean_dist, powerset, Gravity,
                            Rectangle, StrutPartial, UsableRegion, XInitError)

# Ensure code coverage is accurate
from quicktile import __main__  # pylint: disable=unused-import

# Silence flake8 since PyLint already took the line comment spot
__main__  # pylint: disable=pointless-statement

log = logging.getLogger(__name__)

if sys.version_info[0] == 2 and sys.version_info[1] < 7:  # pragma: no cover
    import unittest2 as unittest
else:                                                     # pragma: no cover
    import unittest

MYPY = False
if MYPY:  # pragma: nocover
    # pylint: disable=unused-import
    from typing import Tuple  # NOQA

# Set up a nice, oddly-shaped fake desktop made from screens
# I actually have access to (though not all on the same PC)
MOCK_SCREENS = [
    Rectangle(0, 0, 1280, 1024),
    Rectangle(1280, 0, 1280, 1024),
    Rectangle(0, 1024, 1680, 1050),
    Rectangle(1680, 1024, 1440, 900)
]

# pylint: disable=too-few-public-methods


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

    def test_euclidean_dist(self):  # type: () -> None
        """euclidean_dist: basic functionality"""
        # TODO: Improve type signature

        # Length of 0, commutative
        for x in range(-2, 3):
            for y in range(-2, 3):
                self.assertEqual(euclidean_dist((x, y), (x, y)), 0)

        # Length of 1, commutative
        for vec_a, vec_b in (
                ((0, 0), (1, 0)),
                ((0, 0), (0, 1)),
                ((0, 0), (-1, 0)),
                ((0, 0), (0, -1)),
                ((0, -1), (0, -2)),
                ((0, -5), (0, -6)),
                ((2, 1), (3, 1)),
                ((0, 5), (0, 4))):
            self.assertEqual(euclidean_dist(vec_b, vec_a), 1)
            self.assertEqual(euclidean_dist(vec_a, vec_b), 1)

        # Integer input, floating-point output
        self.assertAlmostEqual(euclidean_dist((1, 2), (4, 5)), 4.24264068)
        self.assertAlmostEqual(euclidean_dist((4, 5), (1, 2)), 4.24264068)

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
                # Workaround for MyPy thinking `expected` isn't a list
                for item in subset:  # type: ignore
                    self.assertIn(item, test_set)

            # Check that ALL subsets are returned
            # FIXME: This shouldn't enforce an ordering constraint.
            self.assertEqual(list(powerset([1, 2, 3])), expected)

    # TODO: Test fmt_table

    # TODO: Test _make_positions

    def test_xiniterror_str(self):  # type: () -> None
        """XInitError.__str__ output contains provided text"""
        self.assertIn("Testing 123", str(XInitError("Testing 123")))


class TestStrutPartial(unittest.TestCase):
    """Tests for my custom _NET_WM_STRUT_PARTIAL wrapper class"""

    def test_construction(self):
        """StrutPartial: construction"""
        self.assertEqual(StrutPartial(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12),
            StrutPartial(left=1, right=2, top=3, bottom=4,
            left_start_y=5, left_end_y=6, right_start_y=7, right_end_y=8,
            top_start_x=9, top_end_x=10, bottom_start_x=11, bottom_end_x=12))

    def test_as_rects(self):
        """StrutPartial: as_rects (basic function)"""
        test_struts = [
            StrutPartial(left=1, right=2, top=3, bottom=4),
            StrutPartial(
                left=1, right=2, top=3, bottom=4,
                left_start_y=5, left_end_y=6, right_start_y=7, right_end_y=8,
                top_start_x=9, top_end_x=10,
                bottom_start_x=11, bottom_end_x=12),
            StrutPartial(left=5000, right=6000, top=7000, bottom=8000),
            StrutPartial(
                left=1, right=2, top=3, bottom=4,
                left_start_y=-2000, left_end_y=3000,
                right_start_y=-4000, right_end_y=5000,
                top_start_x=-6000, top_end_x=7000,
                bottom_start_x=-8000, bottom_end_x=9000),
            StrutPartial(
                left=1, right=2, top=3, bottom=4,
                left_start_y=2000, left_end_y=-3000,
                right_start_y=4000, right_end_y=-5000,
                top_start_x=6000, top_end_x=-7000,
                bottom_start_x=8000, bottom_end_x=-9000),
        ]

        for dtop_rect in (Rectangle(0, 0, 20, 30), Rectangle(40, 50, 70, 80)):
            print("Desktop Rectangle: ", dtop_rect)
            for strut in test_struts:
                print("Desktop Rectangle: ", dtop_rect, " | Strut: ", strut)
                self.assertEqual(strut.as_rects(dtop_rect), [x for x in (
                    # Left
                    Rectangle(x=dtop_rect.x, y=strut.left_start_y,
                        width=strut.left, y2=strut.left_end_y
                              ).intersect(dtop_rect),
                    # Right
                    Rectangle(x=dtop_rect.x2, y=strut.right_start_y,
                        width=-strut.right, y2=strut.right_end_y
                              ).intersect(dtop_rect),
                    # Top
                    Rectangle(x=strut.top_start_x, y=dtop_rect.y,
                        x2=strut.top_end_x, height=strut.top
                              ).intersect(dtop_rect),
                    # Bottom
                    Rectangle(x=strut.bottom_start_x, y=dtop_rect.y2,
                        x2=strut.bottom_end_x, height=-strut.bottom
                              ).intersect(dtop_rect)) if x])

    def test_as_rects_pruning(self):
        """StrutPartial: as_rects doesn't return empty rects"""
        dtop_rect = Rectangle(1, 2, 30, 40)
        self.assertEqual(
            StrutPartial(5, 0, 0, 0).as_rects(dtop_rect),
            [Rectangle(x=1, y=2, width=5, height=40)])
        self.assertEqual(
            StrutPartial(0, 6, 0, 0).as_rects(dtop_rect),
            [Rectangle(x=dtop_rect.x2 - 6, y=2, width=6, height=40)])
        self.assertEqual(
            StrutPartial(0, 0, 7, 0).as_rects(dtop_rect),
            [Rectangle(x=1, y=2, width=30, height=7)])
        self.assertEqual(
            StrutPartial(0, 0, 0, 8).as_rects(dtop_rect),
            [Rectangle(x=1, y=dtop_rect.y2 - 8, width=30, height=8)])


class TestRectangle(unittest.TestCase):
    """Tests for my custom Rectangle class"""

    def setUp(self):
        """Implicitly test positional and keyword construction during setup"""
        self.rect1 = Rectangle(1, 2, 3, 4)
        self.rect2 = Rectangle(x=2, y=3, width=4, height=5)
        self.rect3 = Rectangle(-1, -2, x2=3, y2=4)

    def test_member_access(self):
        """Rectangle: quacks like a namedtuple"""
        self.assertEqual(self.rect1[0], 1)
        self.assertEqual(self.rect1.y, 2)
        self.assertEqual(self.rect1, (1, 2, 3, 4))

    def test_properties(self):
        """Rectangle: convenience properties"""
        for rect in (self.rect1, self.rect2, self.rect3):
            self.assertEqual(rect.x2, rect.x + rect.width)
            self.assertEqual(rect.y2, rect.y + rect.height)
            self.assertEqual(rect.xy, (rect.x, rect.y))

    def test_negative_size(self):
        """Rectangle: test normalization of negative sizes"""
        self.assertEqual(Rectangle(3, 2, -2, 2), (1, 2, 2, 2))
        self.assertEqual(Rectangle(1, 4, 2, -2), (1, 2, 2, 2))
        self.assertEqual(Rectangle(3, 4, -2, -2), (1, 2, 2, 2))

    def test_float_input(self):
        """Rectangle: test truncating of float inputs to integers"""
        test_rect = Rectangle(1.0, 0.5, 1.3, 2.8)
        self.assertIsInstance(test_rect.x, int)
        self.assertIsInstance(test_rect.y, int)
        self.assertIsInstance(test_rect.width, int)
        self.assertIsInstance(test_rect.height, int)
        self.assertEqual(test_rect.x, 1)
        self.assertEqual(test_rect.y, 0)
        self.assertEqual(test_rect.width, 1)
        self.assertEqual(test_rect.height, 2)

    def test_none_safe(self):  # pylint: disable=no-self-use
        """Rectangle: __new__ doesn't attempt to compare None and int"""
        Rectangle(0, 0, width=None, height=None, x2=0, y2=0)

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

    def test_contains(self):
        """Rectangle: __contains__"""
        # Wholly-contained == True
        self.assertTrue(Rectangle(2, 2, 1, 1) in Rectangle(1, 1, 3, 3))
        self.assertTrue(Rectangle(1, 1, 3, 1) in Rectangle(1, 1, 3, 3))
        self.assertTrue(Rectangle(1, 1, 1, 3) in Rectangle(1, 1, 3, 3))
        # ...including for empty rectangles
        self.assertTrue(Rectangle(1, 1, 0, 0) in Rectangle(1, 1, 0, 0))
        self.assertTrue(Rectangle(1, 1, 0, 0) in Rectangle(1, 1, 3, 3))
        self.assertTrue(Rectangle(4, 4, 0, 0) in Rectangle(1, 1, 3, 3))

        # Mere overlap isn't enough
        self.assertFalse(Rectangle(0, 0, 3, 3) in Rectangle(1, 1, 3, 3))
        self.assertFalse(Rectangle(2, 0, 3, 3) in Rectangle(1, 1, 3, 3))
        self.assertFalse(Rectangle(0, 2, 3, 3) in Rectangle(1, 1, 3, 3))
        self.assertFalse(Rectangle(2, 2, 3, 3) in Rectangle(1, 1, 3, 3))

        # Type mismatches don't cause errors
        self.assertNotIn(1, Rectangle(0, 0, 2, 2))

    def test_intersect(self):
        """Rectangle: intersection"""
        self.assertEqual(self.rect1.intersect(self.rect2),
                         Rectangle(2, 3, 2, 3))
        self.assertEqual(self.rect2.intersect(self.rect1),
                         Rectangle(2, 3, 2, 3))

        # Basic test that unrecognized types fail properly
        with self.assertRaises(TypeError):
            print(self.rect1.intersect(5))

    def test_to_point(self):
        """Rectangle: to_point"""
        for rectangle in (self.rect1, self.rect2, self.rect3):
            point = rectangle.to_point()

            self.assertEqual(point, (rectangle.x, rectangle.y, 0, 0))

    def test_union(self):
        """Rectangle: union finds bounding box for two rectangles"""
        self.assertEqual(self.rect1.union(self.rect2), Rectangle(
            self.rect1.x, self.rect1.y,
            self.rect2.x2 - self.rect1.x,
            self.rect2.y2 - self.rect1.y))
        self.assertEqual(self.rect2.union(self.rect1), Rectangle(
            self.rect1.x, self.rect1.y,
            self.rect2.x2 - self.rect1.x,
            self.rect2.y2 - self.rect1.y))
        self.assertEqual(Rectangle(-2, -5, 1, 1).union(Rectangle(2, 5, 1, 1)),
                         Rectangle(-2, -5, x2=3, y2=6))

        # Basic test that unrecognized types fail properly
        with self.assertRaises(TypeError):
            print(self.rect1.union(5))

    def test_moved_into(self):
        """Rectangle: moved_into"""

        display = Rectangle(0, 0, 1280, 1024)

        # Clipping
        self.assertEqual(Rectangle(0, 0, 100, 200).moved_into(display),
                         Rectangle(0, 0, 100, 200))
        self.assertEqual(Rectangle(-1, -1, 100, 200).moved_into(display),
                         Rectangle(0, 0, 100, 200))
        self.assertEqual(Rectangle(1200, -1, 100, 200).moved_into(display),
                         Rectangle(1280 - 100, 0, 100, 200))
        self.assertEqual(Rectangle(-1, 1000, 100, 200).moved_into(display),
                         Rectangle(0, 1024 - 200, 100, 200))
        self.assertEqual(Rectangle(1200, -1, 2000, 200).moved_into(display),
                         Rectangle(0, 0, 1280, 200))
        self.assertEqual(Rectangle(-1, 1000, 100, 2000).moved_into(display),
                         Rectangle(0, 0, 100, 1024))
        self.assertEqual(Rectangle(-1200, 1, 2000, 200).moved_into(display),
                         Rectangle(0, 1, 1280, 200))
        self.assertEqual(Rectangle(1, -1000, 100, 2000).moved_into(display),
                         Rectangle(1, 0, 100, 1024))

        # No Clipping
        self.assertEqual(Rectangle(0, 0, 100, 200).moved_into(display, False),
                         Rectangle(0, 0, 100, 200))
        self.assertEqual(Rectangle(-1, -1, 10, 20).moved_into(display, False),
                         Rectangle(0, 0, 10, 20))
        self.assertEqual(Rectangle(1200, -1, 100, 200).moved_into(display,
                         False), Rectangle(1280 - 100, 0, 100, 200))
        self.assertEqual(Rectangle(-1, 1000, 100, 200).moved_into(display,
                         False), Rectangle(0, 1024 - 200, 100, 200))
        self.assertEqual(Rectangle(1200, -1, 2000, 200).moved_into(display,
                         False), Rectangle(0, 0, 2000, 200))
        self.assertEqual(Rectangle(-1, 1000, 100, 2000).moved_into(display,
                         False), Rectangle(0, 0, 100, 2000))
        self.assertEqual(Rectangle(-1200, 1, 2000, 200).moved_into(display,
                         False), Rectangle(0, 1, 2000, 200))
        self.assertEqual(Rectangle(1, -1000, 100, 2000).moved_into(display,
                         False), Rectangle(1, 0, 100, 2000))

    def test_subtract(self):
        """Rectangle: subtract"""
        # Subtracting a non-intersecting rectangle returns self
        self.assertIs(self.rect1.subtract(Rectangle(10, 10, 1, 1)), self.rect1)

        # Basic checks that subtracting chops off the correct edge
        rect = Rectangle(x=2, y=4, x2=8, y2=12)
        print("Testing subtracting from ", rect)
        for length, thickness in ((5, 2), (7, 2), (5, 10), (10, 10)):
            print(length, thickness)
            self.assertEqual(rect.subtract(
                Rectangle(x=rect.x + 5, y=rect.y + 2,
                          width=-length, height=-thickness)),
                Rectangle(x=2, y=4 + 2, x2=8, y2=12))
            self.assertEqual(rect.subtract(
                Rectangle(x=rect.x2 - 5, y=rect.y2 - 2,
                          width=length, height=thickness)),
                Rectangle(x=2, y=4, x2=8, y2=12 - 2))
            self.assertEqual(rect.subtract(
                Rectangle(x=rect.x + 2, y=rect.y + 5,
                          width=-thickness, height=-length)),
                Rectangle(x=2 + 2, y=4, x2=8, y2=12))
            self.assertEqual(rect.subtract(
                Rectangle(x=rect.x2 - 2, y=rect.y2 - 5,
                          width=thickness, height=length)),
                Rectangle(x=2, y=4, x2=8 - 2, y2=12))

    def test_relative_conversion_basic(self):
        """Rectangle: converting to/from relative coordinates works"""
        # Test with explicit, known values
        ref_rect = Rectangle(-10, 5, 0, 0)
        start_rect = Rectangle(1, 2, 3, 4)
        expected_rect = Rectangle(11, -3, 3, 4)

        rel_rect = start_rect.to_relative(ref_rect)
        self.assertEqual(rel_rect, expected_rect)
        self.assertEqual(rel_rect.from_relative(ref_rect), start_rect)

    def test_rel_conversion_symmetry(self):
        """Rectangle: converting to/from relative coordinates is symmetrical"""
        # Test a variety of combinations
        for ref_rect in (Rectangle(0, 0, 100, 200), Rectangle(-30, -40, 0, 0),
                Rectangle(300, 400, 0, 0), Rectangle(-200, -200, 1000, 1000)):
            for test_rect in (Rectangle(0, 0, 3, 0), Rectangle(-1000, 0, 1, 2),
                    Rectangle(1000, 1000, 100, 100), Rectangle(10, 10, 10, 1)):
                rel_rect = test_rect.to_relative(ref_rect)
                self.assertEqual(test_rect, rel_rect.from_relative(ref_rect))

    def test_gravity_noop(self):  # type: () -> None
        """Rectangle: gravity conversions on top-left corner are no-ops."""
        start_rect = Rectangle(x=2, y=4, width=8, height=6)
        self.assertEqual(start_rect, start_rect.to_gravity(Gravity.TOP_LEFT))
        self.assertEqual(start_rect,
            start_rect.from_gravity(Gravity.TOP_LEFT))

    def test_gravity_conversion(self):
        """Rectangle: basic gravity conversions"""

        # Basic test with center gravity and an even width and height
        start_rect = Rectangle(x=2, y=4, width=8, height=6)
        grav_rect = start_rect.to_gravity(Gravity.CENTER)
        self.assertEqual(grav_rect, Rectangle(x=6, y=7, width=8, height=6))
        self.assertEqual(grav_rect.from_gravity(Gravity.CENTER), start_rect)

        # Test all combinations in a slightly less transparent manner
        for edge in (100, 200):
            ehalf = edge / 2
            for gravity, expect in (
                    (Gravity.TOP_LEFT, (0, 0)),
                    (Gravity.TOP, (ehalf, 0)),
                    (Gravity.TOP_RIGHT, (edge, 0)),
                    (Gravity.LEFT, (0, ehalf)),
                    (Gravity.CENTER, (ehalf, ehalf)),
                    (Gravity.RIGHT, (edge, ehalf)),
                    (Gravity.BOTTOM_LEFT, (0, edge)),
                    (Gravity.BOTTOM, (ehalf, edge)),
                    (Gravity.BOTTOM_RIGHT, (edge, edge))):
                rect = Rectangle(0, 0, edge, edge)

                grav_rect = rect.to_gravity(gravity)
                self.assertEqual(grav_rect.to_point(),
                    Rectangle(rect.x + expect[0], rect.y + expect[1], 0, 0))
                self.assertEqual(rect, grav_rect.from_gravity(gravity))

    def test_gravity_rounding(self):
        """Rectangle: gravity conversions truncate predictably"""
        self.assertEqual(
            Rectangle(3, 5, 7, 9).to_gravity(Gravity.CENTER),
            Rectangle(6, 9, 7, 9))

    def test_gdk_round_tripping(self):
        """Rectangle: from_gdk/to_gdk"""

        test_rect1 = Rectangle(1, 2, 3, 4)
        test_rect2 = Rectangle(5, 6, 7, 8)

        gdk_rect1 = test_rect1.to_gdk()
        gdk_rect2 = test_rect2.to_gdk()

        # To make sure we're not just setting dummy properties, test the
        # results of GdkRectangle's union operator against ours.
        result = Rectangle.from_gdk(gdk_rect1.union(gdk_rect2))
        control = test_rect1.union(test_rect2)

        self.assertEqual(result, control)

    def test_two_point_form(self):
        """Rectangle: two-point-form properties function properly"""
        self.assertEqual(self.rect1.x2, self.rect1.x + self.rect1.width)
        self.assertEqual(self.rect1.y2, self.rect1.y + self.rect1.height)


class TestUsableRegion(unittest.TestCase):
    """Tests for my per-monitor _NET_WORKAREA calculation class"""

    def test_bool(self):
        """UsableRegion: __bool__"""
        # Empty regions are falsy
        test_region = UsableRegion()
        self.assertFalse(test_region)

        # Regions containing non-empty monitors are truthy
        test_region.set_monitors([Rectangle(0, 0, 1920, 1080)])
        test_region.set_monitors([Rectangle(1280, 1024, 1920, 1080)])
        self.assertTrue(test_region)

        # Regions containing only empty monitors are falsy
        mon1 = Rectangle(5, 10, 0, 0)
        test_region.set_monitors([Rectangle(0, 0, 0, 0)])
        self.assertFalse(test_region)

        # Force a denormalized region to verify that empty rectangles are still
        # treated as falsy
        # pylint: disable=protected-access
        test_region._monitors = [mon1]
        test_region._usable = {mon1: mon1}
        self.assertFalse(test_region)

        # TODO: Figure out how `Virtual` settings larger than the physical
        #       resolution look to these APIs and then pin down and test the
        #       behaviour for setting desktop rectangles that aren't the union
        #       of the monitor rectangles.
        #       (`Virtual` is the Xorg.conf setting which allows you to scroll
        #       around a desktop bigger that what the monitors show.)

    def test_find_usable_rect(self):
        """UsableRegion: find_usable_rect"""
        test_region = UsableRegion()

        # Actual rectangles of my monitors
        # TODO: Double-check that this matches the real-world API outputs
        #       (eg. make sure there are no lurking off-by-one errors)
        test_region.set_monitors([
            Rectangle(0, 56, 1280, 1024),
            Rectangle(1280, 0, 1920, 1080),
            Rectangle(3200, 56, 1280, 1024)])

        # Actual struts harvested from my desktop's panels
        # (Keep the empty struts at the beginning and end. One from an
        #  auto-hiding Plasma 5 panel caught an early bug where
        #  only the last strut subtracted from a monitor was retained)
        test_region.set_panels([
            StrutPartial(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
            StrutPartial(0, 0, 0, 30, 0, 0, 0, 0, 0, 0, 3200, 4479),
            StrutPartial(0, 0, 0, 30, 0, 0, 0, 0, 0, 0, 1280, 3199),
            StrutPartial(0, 0, 0, 30, 0, 0, 0, 0, 0, 0, 0, 1279),
            StrutPartial(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        ])

        # Out-of-bounds Space (no fallback)
        self.assertEqual(test_region.find_usable_rect(
            Rectangle(-3, 1, 1, 1), fallback=False), None)
        self.assertEqual(test_region.find_usable_rect(
            Rectangle(200, -5, 1, 1), fallback=False), None)
        self.assertEqual(test_region.find_usable_rect(
            Rectangle(5000, 200, 1, 1), False), None)
        self.assertEqual(test_region.find_usable_rect(
            Rectangle(200, 5000, 1, 1), False), None)

        # Out-of-bounds Space (fallback)
        self.assertEqual(test_region.find_usable_rect(
            Rectangle(-3, 1, 1, 1)), Rectangle(0, 56, 1280, 994))
        self.assertEqual(test_region.find_usable_rect(
            Rectangle(200, -5, 1, 1)), Rectangle(0, 56, 1280, 994))
        self.assertEqual(test_region.find_usable_rect(
            Rectangle(5000, 200, 1, 1)), Rectangle(3200, 56, 1280, 994))
        self.assertEqual(test_region.find_usable_rect(
            Rectangle(200, 5000, 1, 1)), Rectangle(0, 56, 1280, 994))

        # Dead Space (no fallback)
        self.assertEqual(test_region.find_usable_rect(
            Rectangle(1, 1, 1, 1), fallback=False), None)
        self.assertEqual(test_region.find_usable_rect(
            Rectangle(3203, 1, 1, 1), False), None)

        # Dead Space (fallback)
        self.assertEqual(test_region.find_usable_rect(
            Rectangle(1, 1, 1, 1)), Rectangle(0, 56, 1280, 994))
        self.assertEqual(test_region.find_usable_rect(
            Rectangle(3203, 1, 1, 1)), Rectangle(3200, 56, 1280, 994))

        # Reserved Space (no fallback)
        self.assertEqual(test_region.find_usable_rect(
            Rectangle(0, 1277, 1, 1), fallback=False), None)
        self.assertEqual(test_region.find_usable_rect(
            Rectangle(0, 2000, 1, 1), False), None)
        self.assertEqual(test_region.find_usable_rect(
            Rectangle(3000, 2000, 1, 1), False), None)
        self.assertEqual(test_region.find_usable_rect(
            Rectangle(3400, 1277, 1, 1), False), None)

        # Reserved Space (fallback)
        self.assertEqual(test_region.find_usable_rect(
            Rectangle(0, 1277, 1, 1)), Rectangle(0, 56, 1280, 994))
        self.assertEqual(test_region.find_usable_rect(
            Rectangle(0, 2000, 1, 1)), Rectangle(0, 56, 1280, 994))
        self.assertEqual(test_region.find_usable_rect(
            Rectangle(3000, 2000, 1, 1)), Rectangle(1280, 0, 1920, 1050))
        self.assertEqual(test_region.find_usable_rect(
            Rectangle(3400, 1277, 1, 1)), Rectangle(3200, 56, 1280, 994))

        # Available Space
        self.assertEqual(test_region.find_usable_rect(
            Rectangle(10, 640, 1, 1)),
            Rectangle(x=0, y=56, width=1280, height=994))
        self.assertEqual(test_region.find_usable_rect(
            Rectangle(3000, 640, 1, 1)),
            Rectangle(x=1280, y=0, width=1920, height=1050))
        self.assertEqual(test_region.find_usable_rect(
            Rectangle(3300, 640, 1, 1)),
            Rectangle(x=3200, y=56, width=1280, height=994))

        # TODO: Test edge pixels for off-by-one errors

    def test_update_typecheck(self):
        """UsableRegion: type enforcement for internal _update function"""
        test_region = UsableRegion()
        with self.assertRaises(TypeError):
            # Must be a *list* of Rectangles
            test_region.set_monitors(Rectangle(0, 0, 1280, 1024))

        test_region = UsableRegion()
        with self.assertRaises(TypeError):
            # Use a tuple as a test because, just because it's a namedtuple
            # doesn't mean we want *any* tuple with the right arity
            test_region.set_monitors([(0, 0, 1280, 1024)])

        test_region = UsableRegion()
        with self.assertRaises(TypeError):
            # Must be a *list* of StrutPartials
            test_region.set_panels(
                StrutPartial(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12))

        test_region = UsableRegion()
        with self.assertRaises(TypeError):
            # Use a tuple as a test because, just because it's a namedtuple
            # doesn't mean we want *any* tuple with the right arity
            test_region.set_panels([(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12)])

    def test_update_nonempty(self):
        """UsableRegion: only add non-empty entries to _usable"""

        mon1 = Rectangle(1280, 0, 1280, 1024)
        test_region = UsableRegion()
        test_region.set_monitors([mon1,
            Rectangle(0, 0, 100, 0),
            Rectangle(0, 0, 0, 100),
            Rectangle(0, 0, 0, 0)])

        # pylint: disable=protected-access
        self.assertEqual(list(test_region._usable.keys()),
            [Rectangle(1280, 0, 1280, 1024)])

    def test_repr(self):
        """UsableRegion: __repr__"""
        test_region = UsableRegion()
        self.assertEqual(repr(test_region), "Region(<Monitors=[], Struts=[]>)")

        test_region.set_monitors([Rectangle(1, 2, 3, 4)])
        self.assertEqual(repr(test_region), "Region("
            "<Monitors=[Rectangle(x=1, y=2, width=3, height=4)], Struts=[]>)")

        test_region.set_panels(
            [StrutPartial(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12)])
        self.assertEqual(repr(test_region), "Region(<"
            "Monitors=[Rectangle(x=1, y=2, width=3, height=4)], "
            "Struts=[StrutPartial(left=1, right=2, top=3, bottom=4, "
            "left_start_y=5, left_end_y=6, right_start_y=7, right_end_y=8, "
            "top_start_x=9, top_end_x=10, bottom_start_x=11, bottom_end_x=12)]"
            ">)")

# vim: set sw=4 sts=4 expandtab :
