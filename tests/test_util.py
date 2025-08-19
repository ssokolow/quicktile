# -*- coding: utf-8 -*-
"""Tests for ``quicktile.util`` module"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

import unittest

from quicktile.util import (clamp_idx, euclidean_dist, powerset,
    Edge, Gravity, Rectangle, StrutPartial, UsableRegion, XInitError)


class TestHelpers(unittest.TestCase):
    """Tests for loose functions

    .. todo:: Switch to pytest_ to get the ``assertEqual`` readout from assert
       in bare functions.

    .. _pytest: https://docs.pytest.org/
    """

    def test_clamp_idx_default(self):
        """Test that clamp_idx defaults to wrapping behaviour"""
        for x in range(-5, 15):
            self.assertEqual(clamp_idx(x, 10), clamp_idx(x, 10, wrap=True))

    def test_clamp_idx_wrap(self):
        """Test that clamp_idx(wrap=True) wraps as expected"""
        self.assertEqual(clamp_idx(5, 10, wrap=True), 5)
        self.assertEqual(clamp_idx(-1, 10, wrap=True), 9)
        self.assertEqual(clamp_idx(11, 10, wrap=True), 1)
        self.assertEqual(clamp_idx(15, 10, wrap=True), 5)

    def test_clamp_idx(self):
        """Test that clamp_idx(wrap=False) saturates as expected"""
        self.assertEqual(clamp_idx(5, 10, wrap=False), 5)
        self.assertEqual(clamp_idx(-1, 10, wrap=False), 0)
        self.assertEqual(clamp_idx(11, 10, wrap=False), 9)
        self.assertEqual(clamp_idx(15, 10, wrap=False), 9)

    def test_euclidean_dist(self):
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
                # Workaround for MyPy thinking `expected` isn't a list
                for item in subset:
                    self.assertIn(item, test_set)

            # Check that ALL subsets are returned
            self.assertEqual(list(powerset([1, 2, 3])), expected)

    def test_xiniterror_str(self):
        """XInitError.__str__ output contains provided text"""
        self.assertIn("Testing 123", str(XInitError("Testing 123")))


class TestStrutPartial(unittest.TestCase):
    """Tests for my custom ``_NET_WM_STRUT_PARTIAL`` wrapper class"""

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
                    (Edge.LEFT, Rectangle(x=dtop_rect.x, y=strut.left_start_y,
                        width=strut.left, y2=strut.left_end_y
                                          ).intersect(dtop_rect)),
                    # Right
                    (Edge.RIGHT, Rectangle(
                        x=dtop_rect.x2, y=strut.right_start_y,
                        width=-strut.right, y2=strut.right_end_y
                              ).intersect(dtop_rect)),
                    # Top
                    (Edge.TOP, Rectangle(x=strut.top_start_x, y=dtop_rect.y,
                        x2=strut.top_end_x, height=strut.top
                                         ).intersect(dtop_rect)),
                    # Bottom
                    (Edge.BOTTOM, Rectangle(
                        x=strut.bottom_start_x, y=dtop_rect.y2,
                        x2=strut.bottom_end_x, height=-strut.bottom
                              ).intersect(dtop_rect))) if x[1]])

    def test_as_rects_pruning(self):
        """StrutPartial: as_rects doesn't return empty rects"""
        dtop_rect = Rectangle(1, 2, 30, 40)
        self.assertEqual(
            StrutPartial(5, 0, 0, 0).as_rects(dtop_rect),
            [(Edge.LEFT, Rectangle(x=1, y=2, width=5, height=40))])
        self.assertEqual(
            StrutPartial(0, 6, 0, 0).as_rects(dtop_rect),
            [(Edge.RIGHT, Rectangle(
                x=dtop_rect.x2 - 6, y=2, width=6, height=40))])
        self.assertEqual(
            StrutPartial(0, 0, 7, 0).as_rects(dtop_rect),
            [(Edge.TOP, Rectangle(x=1, y=2, width=30, height=7))])
        self.assertEqual(
            StrutPartial(0, 0, 0, 8).as_rects(dtop_rect),
            [(Edge.BOTTOM, Rectangle(
                x=1, y=dtop_rect.y2 - 8, width=30, height=8))])


class TestRectangle(unittest.TestCase):  # pylint: disable=R0904
    """Tests for my custom `Rectangle` class"""

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
            self.assertEqual(rect.area, rect.width * rect.height)

        self.assertEqual(Rectangle(0, 0, 0, 0).area, 0)
        self.assertEqual(Rectangle(0, 0, 10, 0).area, 0)
        self.assertEqual(Rectangle(0, 0, 0, 10).area, 0)

    def test_negative_size(self):
        """Rectangle: test normalization of negative sizes"""
        self.assertEqual(Rectangle(3, 2, -2, 2), (1, 2, 2, 2))
        self.assertEqual(Rectangle(1, 4, 2, -2), (1, 2, 2, 2))
        self.assertEqual(Rectangle(3, 4, -2, -2), (1, 2, 2, 2))

    def test_float_input(self):
        """Rectangle: test truncating of float inputs to integers"""
        test_rect = Rectangle(1.0, 0.5, 1.3, 2.8)  # type: ignore
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

    def test_righthand_construction(self):
        """Rectangle: test construction using x2/y2 and width/height"""
        # Regular
        self.assertEqual(Rectangle(width=2, height=2, x2=3, y2=4),
                         (1, 2, 2, 2))

        # Origin-crossing
        self.assertEqual(Rectangle(width=5, height=8, x2=3, y2=4),
                         (-2, -4, 5, 8))

        # Negative width and/or height
        self.assertEqual(Rectangle(x2=1, y2=4, width=-2, height=2),
                         (1, 2, 2, 2))
        self.assertEqual(Rectangle(x2=3, y2=2, width=2, height=-2),
                         (1, 2, 2, 2))
        self.assertEqual(Rectangle(x2=1, y2=2, width=-2, height=-2),
                         (1, 2, 2, 2))

        self.assertEqual(Rectangle(x2=-3, y2=-2, width=-2, height=2),
                         (-3, -4, 2, 2))
        self.assertEqual(Rectangle(x2=-1, y2=-4, width=2, height=-2),
                         (-3, -4, 2, 2))
        self.assertEqual(Rectangle(x2=-3, y2=-4, width=-2, height=-2),
                         (-3, -4, 2, 2))

        self.assertEqual(Rectangle(x2=-1, y2=4, width=-4, height=6),
                         (-1, -2, 4, 6))
        self.assertEqual(Rectangle(x2=3, y2=-2, width=4, height=-6),
                         (-1, -2, 4, 6))
        self.assertEqual(Rectangle(x2=-1, y2=-2, width=-4, height=-6),
                         (-1, -2, 4, 6))

        # Bad argument combinations
        with self.assertRaises(ValueError):
            Rectangle(x2=1, y2=2, width=3, height=4, x=5)
        with self.assertRaises(ValueError):
            Rectangle(x2=1, y2=2, width=3, height=4, y=6)

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
            print(self.rect1.intersect(5))  # type: ignore

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
            print(self.rect1.union(5))  # type: ignore

    def test_moved_into(self):
        """Rectangle: moved_into"""

        display = Rectangle(0, 0, 1280, 1024)

        self.assertEqual(Rectangle(0, 0, 100, 200).moved_into(display),
                         Rectangle(0, 0, 100, 200))
        self.assertEqual(Rectangle(-1, -1, 10, 20).moved_into(display),
                         Rectangle(0, 0, 10, 20))
        self.assertEqual(Rectangle(1200, -1, 100, 200).moved_into(display),
                         Rectangle(1280 - 100, 0, 100, 200))
        self.assertEqual(Rectangle(-1, 1000, 100, 200).moved_into(display),
                         Rectangle(0, 1024 - 200, 100, 200))
        self.assertEqual(Rectangle(1200, -1, 2000, 200).moved_into(display),
                         Rectangle(0, 0, 2000, 200))
        self.assertEqual(Rectangle(-1, 1000, 100, 2000).moved_into(display),
                         Rectangle(0, 0, 100, 2000))
        self.assertEqual(Rectangle(-1200, 1, 2000, 200).moved_into(display),
                         Rectangle(0, 1, 2000, 200))
        self.assertEqual(Rectangle(1, -1000, 100, 2000).moved_into(display),
                         Rectangle(1, 0, 100, 2000))

        # Wrong Type
        with self.assertRaises(TypeError):
            Rectangle(0, 0, 0, 0).moved_into("hello")  # type: ignore

    def test_moved_off_of(self):
        """Rectangle: moved_off_of"""
        # Moving off a non-intersecting rectangle returns self
        self.assertIs(self.rect1.moved_off_of(Rectangle(10, 10, 1, 1)),
            self.rect1)

        # Basic checks that moved_off_of pushes in the right direction
        rect = Rectangle(x=2, y=4, x2=8, y2=12)
        print("Testing moved_off_of ", rect)
        for length, thickness in ((5, 2), (7, 2), (5, 10), (10, 10)):
            print(length, thickness)
            self.assertEqual(rect.moved_off_of(
                Rectangle(x=rect.x + 5, y=rect.y + 2,
                          width=-length, height=-thickness)),
                rect._replace(y=4 + 2))
            self.assertEqual(rect.moved_off_of(
                Rectangle(x=rect.x2 - 5, y=rect.y2 - 2,
                          width=length, height=thickness)),
                rect._replace(y=4 - 2))
            self.assertEqual(rect.moved_off_of(
                Rectangle(x=rect.x + 2, y=rect.y + 5,
                          width=-thickness, height=-length)),
                rect._replace(x=2 + 2))
            self.assertEqual(rect.moved_off_of(
                Rectangle(x=rect.x2 - 2, y=rect.y2 - 5,
                          width=thickness, height=length)),
                rect._replace(x=2 - 2))

        # Regression test for a real-world "pushes in the wrong direction"
        self.assertEqual(
            Rectangle(x=0, y=1046, width=6, height=34).moved_off_of(
                Rectangle(x=0, y=1050, width=1279, height=30)),
            Rectangle(x=0, y=1016, width=6, height=34))

        # Regression test for "using only area of overlap causes it to go crazy
        # when the rectangle is entirely within the reserved area"
        self.assertEqual(
            Rectangle(x=200, y=1055, width=8, height=9).moved_off_of(
                Rectangle(x=0, y=1050, width=1279, height=30)),
            Rectangle(x=200, y=1041, width=8, height=9))

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

        # Regression test for a real-world "chops off the right edge" error
        self.assertEqual(Rectangle(x=0, y=1046, width=6, height=34).subtract(
                Rectangle(x=0, y=1050, width=1279, height=30)),
            Rectangle(x=0, y=1046, width=6, height=4))

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

    def test_gravity_noop(self):
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
    """Tests for my per-monitor ``_NET_WORKAREA`` calculation class"""

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
        self.assertFalse(test_region)

        # TODO: Figure out how `Virtual` settings larger than the physical
        #       resolution look to these APIs and then pin down and test the
        #       behaviour for setting desktop rectangles that aren't the union
        #       of the monitor rectangles.
        #       (`Virtual` is the Xorg.conf setting which allows you to scroll
        #       around a desktop bigger that what the monitors show.)

    def test_find_monitor_for(self):
        """UsableRegion: find_monitor_for"""
        test_region = UsableRegion()

        # No monitors set
        self.assertIsNone(test_region.find_monitor_for(Rectangle(0, 0, 1, 1)))

        # Actual rectangles of my monitors
        # TODO: Double-check that this matches the real-world API outputs
        #       (eg. make sure there are no lurking off-by-one errors)
        test_region.set_monitors([
            Rectangle(0, 56, 1280, 1024),
            Rectangle(1280, 0, 1920, 1080),
            Rectangle(3200, 56, 1280, 1024)])

        # Actual struts harvested from my desktop's panels
        # to verify that it's returning the *monitor* rectangle and not the
        # largest usable rectangle within.
        #
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

        # Out-of-bounds Space
        self.assertEqual(test_region.find_monitor_for(
            Rectangle(-3, 1, 1, 1)), Rectangle(0, 56, 1280, 1024))
        self.assertEqual(test_region.find_monitor_for(
            Rectangle(200, -5, 1, 1)), Rectangle(0, 56, 1280, 1024))
        self.assertEqual(test_region.find_monitor_for(
            Rectangle(5000, 200, 1, 1)), Rectangle(3200, 56, 1280, 1024))
        self.assertEqual(test_region.find_monitor_for(
            Rectangle(200, 5000, 1, 1)), Rectangle(0, 56, 1280, 1024))

        # Dead Space
        self.assertEqual(test_region.find_monitor_for(
            Rectangle(1, 1, 1, 1)), Rectangle(0, 56, 1280, 1024))
        self.assertEqual(test_region.find_monitor_for(
            Rectangle(3203, 1, 1, 1)), Rectangle(3200, 56, 1280, 1024))

        # Space under panels
        self.assertEqual(test_region.find_monitor_for(
            Rectangle(0, 1277, 1, 1)), Rectangle(0, 56, 1280, 1024))
        self.assertEqual(test_region.find_monitor_for(
            Rectangle(0, 2000, 1, 1)), Rectangle(0, 56, 1280, 1024))
        self.assertEqual(test_region.find_monitor_for(
            Rectangle(3000, 2000, 1, 1)), Rectangle(1280, 0, 1920, 1080))
        self.assertEqual(test_region.find_monitor_for(
            Rectangle(3400, 1277, 1, 1)), Rectangle(3200, 56, 1280, 1024))

        # Available Space
        self.assertEqual(test_region.find_monitor_for(
            Rectangle(10, 640, 1, 1)),
            Rectangle(x=0, y=56, width=1280, height=1024))
        self.assertEqual(test_region.find_monitor_for(
            Rectangle(3000, 640, 1, 1)),
            Rectangle(x=1280, y=0, width=1920, height=1080))
        self.assertEqual(test_region.find_monitor_for(
            Rectangle(3300, 640, 1, 1)),
            Rectangle(x=3200, y=56, width=1280, height=1024))

    def test_clip_to_usable_region(self):
        """UsableRegion: clip_to_usable_region"""
        test_region = UsableRegion()

        # Quick integration test for internal call to find_monitor_for
        self.assertIsNone(
            test_region.clip_to_usable_region(Rectangle(0, 0, 1, 1)))

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

        # Out of bounds (no overlap)
        self.assertIsNone(test_region.clip_to_usable_region(  # top
            Rectangle(3200, -4, 3, 4)))
        self.assertIsNone(test_region.clip_to_usable_region(  # right
            Rectangle(4480, 0, 3, 4)))
        self.assertIsNone(test_region.clip_to_usable_region(  # bottom
            Rectangle(3200, 1080, 3, 4)))
        self.assertIsNone(test_region.clip_to_usable_region(  # left
            Rectangle(-3, 100, 3, 4)))

        # Out of bounds (overlap)
        # Top
        bottom = 1024 + 56
        panel = 30
        self.assertEqual(test_region.clip_to_usable_region(
            Rectangle(0, -4, 3, 4 + 56 + 4)), Rectangle(0, 56, 3, 4))
        self.assertEqual(test_region.clip_to_usable_region(
            Rectangle(1920, -4, 3, 4 + 4)), Rectangle(1920, 0, 3, 4))
        # Right
        self.assertEqual(test_region.clip_to_usable_region(
            Rectangle(4480 - 3, 56, 3 + 3, 4)), Rectangle(4480 - 3, 56, 3, 4))
        # Bottom
        self.assertEqual(test_region.clip_to_usable_region(
            Rectangle(0, bottom - panel - 4, 3, 4 + panel + 4)),
            Rectangle(0, bottom - panel - 4, 3, 4))
        self.assertEqual(test_region.clip_to_usable_region(
            Rectangle(1920, 1080 - panel - 4, 3, 4 + panel + 4)),
            Rectangle(1920, 1080 - panel - 4, 3, 4))
        self.assertEqual(test_region.clip_to_usable_region(
            Rectangle(3300, bottom - panel - 4, 3, 4 + panel + 4)),
            Rectangle(3300, bottom - panel - 4, 3, 4))
        # Left
        self.assertEqual(test_region.clip_to_usable_region(
            Rectangle(-3, 100, 6, 4)), Rectangle(0, 100, 6 - 3, 4))

        # Dead Space (no overlap)
        self.assertIsNone(test_region.clip_to_usable_region(
            Rectangle(0, 0, 20, 20)))
        self.assertIsNone(test_region.clip_to_usable_region(
            Rectangle(3200, 0, 20, 20)))

        # Dead Space (overlap)
        self.assertEqual(test_region.clip_to_usable_region(
            Rectangle(0, 0, 80, 80)), Rectangle(0, 56, 80, 80 - 56))
        self.assertEqual(test_region.clip_to_usable_region(
            Rectangle(3200, 0, 80, 80)), Rectangle(3200, 56, 80, 80 - 56))

        # Reserved Space (no overlap)
        self.assertIsNone(test_region.clip_to_usable_region(
            Rectangle(0, 1277, 1, 1)), None)
        self.assertIsNone(test_region.clip_to_usable_region(
            Rectangle(1920, 1060, 1, 1)), None)
        self.assertIsNone(test_region.clip_to_usable_region(
            Rectangle(3200, 1277, 1, 1)), None)

        # Reserved Space (overlap)
        self.assertEqual(test_region.clip_to_usable_region(
            Rectangle(0, bottom - panel - 10, 1, 40)),
            Rectangle(0, bottom - panel - 10, 1, 10))
        self.assertEqual(test_region.clip_to_usable_region(
            Rectangle(1920, 1080 - panel - 10, 1, 40)),
            Rectangle(1920, bottom - panel - 10, 1, 10))
        self.assertEqual(test_region.clip_to_usable_region(
            Rectangle(3200, bottom - panel - 10, 1, 40)),
            Rectangle(3200, bottom - panel - 10, 1, 10))

        # Available Space
        self.assertEqual(test_region.clip_to_usable_region(
            Rectangle(10, 640, 1, 1)),
            Rectangle(10, 640, 1, 1))
        self.assertEqual(test_region.clip_to_usable_region(
            Rectangle(3000, 640, 1, 1)),
            Rectangle(3000, 640, 1, 1))
        self.assertEqual(test_region.clip_to_usable_region(
            Rectangle(3300, 640, 1, 1)),
            Rectangle(3300, 640, 1, 1))

        # TODO: Test edge pixels for off-by-one errors

    def test_move_to_usable_region(self):
        """UsableRegion: move_to_usable_region"""
        test_region = UsableRegion()

        # Quick integration test for internal call to find_monitor_for
        self.assertIsNone(
            test_region.move_to_usable_region(Rectangle(0, 0, 1, 1)))

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

        # Out-of-bounds Space
        bottom = 1024 + 56
        panel = 30
        self.assertEqual(test_region.move_to_usable_region(
            Rectangle(-3, 1, 2, 3)), Rectangle(0, 56, 2, 3))
        self.assertEqual(test_region.move_to_usable_region(
            Rectangle(200, -5, 4, 5)), Rectangle(200, 56, 4, 5))
        self.assertEqual(test_region.move_to_usable_region(
            Rectangle(5000, 200, 6, 7)), Rectangle(4480 - 6, 200, 6, 7))
        self.assertEqual(test_region.move_to_usable_region(
            Rectangle(200, 5000, 8, 31)),
            Rectangle(200, bottom - panel - 31, 8, 31))
        self.assertEqual(test_region.move_to_usable_region(
            Rectangle(2000, 5000, 10, 32)),
            Rectangle(2000, 1080 - panel - 32, 10, 32))
        self.assertEqual(test_region.move_to_usable_region(
            Rectangle(3300, 5000, 12, 33)),
            Rectangle(3300, bottom - panel - 33, 12, 33))

        # Dead Space
        self.assertEqual(test_region.move_to_usable_region(
            Rectangle(1, 2, 3, 4)), Rectangle(1, 56, 3, 4))
        self.assertEqual(test_region.move_to_usable_region(
            Rectangle(3203, 5, 6, 7)), Rectangle(3203, 56, 6, 7))

        # Reserved Space (fallback)
        self.assertEqual(test_region.move_to_usable_region(
            Rectangle(0, bottom - panel - 3, 1, 5)),
            Rectangle(0, bottom - panel - 5, 1, 5))
        self.assertEqual(test_region.move_to_usable_region(
            Rectangle(2000, bottom - panel - 4, 1, 6)),
            Rectangle(2000, bottom - panel - 6, 1, 6))
        self.assertEqual(test_region.move_to_usable_region(
            Rectangle(3300, bottom - panel + 5, 1, 7)),
            Rectangle(3300, bottom - panel - 7, 1, 7))

        # Available Space
        for test_rect in (
            Rectangle(10, 640, 1, 1),
            Rectangle(3000, 640, 1, 1),
            Rectangle(3300, 640, 1, 1),
        ):
            self.assertIs(test_region.move_to_usable_region(test_rect),
                test_rect)

        # TODO: Test edge pixels for off-by-one errors

    def test_issue_45(self):
        """UsableRegion: struts on internal monitor edges work properly

        (Test that the ambiguous aspect of the spec is interpreted in
        accordance with how Unity actually implemented it.)

        """
        # Use the actual --debug geometry from issue 45 so this is also
        # a regression test.
        test_region = UsableRegion()
        test_region.set_monitors([
            Rectangle(0, 0, 1920, 1200), Rectangle(1920, 0, 1920, 1200)])
        test_region.set_panels([StrutPartial(*x) for x in [
            [49, 0, 0, 0, 24, 1199, 0, 0, 0, 0, 0, 0],
            [1969, 0, 0, 0, 24, 1199, 0, 0, 0, 0, 0, 0],
            [0, 0, 24, 0, 0, 0, 0, 0, 0, 1919, 0, 0],
            [0, 0, 24, 0, 0, 0, 0, 0, 1920, 3839, 0, 0]]])
        # Right monitor (easy case)
        self.assertEqual(test_region.clip_to_usable_region(
            Rectangle(1920, 0, 100, 100)),
            Rectangle(x=1969, y=24, width=100 - 49, height=100 - 24))

        # Left monitor (problem case)
        self.assertEqual(test_region.clip_to_usable_region(
            Rectangle(0, 0, 100, 100)),
            Rectangle(x=49, y=24, width=100 - 49, height=100 - 24))

        # Asymmetric monitors (left monitor bigger)
        test_region = UsableRegion()
        test_region.set_monitors([
            Rectangle(0, 0, 1920, 1200), Rectangle(1920, 0, 1280, 1024)])
        test_region.set_panels([StrutPartial(*x) for x in [
            [49, 0, 0, 0, 24, 1199, 0, 0, 0, 0, 0, 0],
            [1969, 0, 0, 0, 24, 1023, 0, 0, 0, 0, 0, 0],
            [0, 0, 24, 0, 0, 0, 0, 0, 0, 1919, 0, 0],
            [0, 0, 24, 0, 0, 0, 0, 0, 1920, 3199, 0, 0]]])
        # Right monitor (easy case)
        self.assertEqual(test_region.clip_to_usable_region(
            Rectangle(1920, 0, 100, 100)),
            Rectangle(x=1969, y=24, width=100 - 49, height=100 - 24))

        # Left monitor (problem case)
        self.assertEqual(test_region.clip_to_usable_region(
            Rectangle(0, 0, 100, 100)),
            Rectangle(x=49, y=24, width=100 - 49, height=100 - 24))

        # Asymmetric monitors (left monitor smaller)
        test_region = UsableRegion()
        test_region.set_monitors([
            Rectangle(0, 0, 1280, 1024), Rectangle(1280, 0, 1920, 1200)])
        test_region.set_panels([StrutPartial(*x) for x in [
            [49, 0, 0, 0, 24, 1023, 0, 0, 0, 0, 0, 0],
            [1329, 0, 0, 0, 24, 1199, 0, 0, 0, 0, 0, 0],
            [0, 0, 24, 0, 0, 0, 0, 0, 0, 1023, 0, 0],
            [0, 0, 24, 0, 0, 0, 0, 0, 1024, 3199, 0, 0]]])
        # Right monitor (easy case)
        self.assertEqual(test_region.clip_to_usable_region(
            Rectangle(1280, 0, 100, 100)),
            Rectangle(x=1329, y=24, width=100 - 49, height=100 - 24))

        # Left monitor (problem case)
        self.assertEqual(test_region.clip_to_usable_region(
            Rectangle(0, 0, 100, 100)),
            Rectangle(x=49, y=24, width=100 - 49, height=100 - 24))

    def test_issue_108(self):
        """UsableRegion: windows use of space left free by narrow panels

        Regression test for #64, #65, and #108.
        """

        test_region = UsableRegion()
        test_region.set_monitors([Rectangle(0, 0, 1920, 1080)])
        test_region.set_panels([StrutPartial(bottom=33,
            bottom_start_x=1022, bottom_end_x=1919)])

        # Left half
        self.assertEqual(test_region.clip_to_usable_region(
            Rectangle(0, 0, 960, 1080)),
            Rectangle(x=0, y=0, width=960, height=1080))

        # Right half
        self.assertEqual(test_region.clip_to_usable_region(
            Rectangle(960, 0, 960, 1080)),
            Rectangle(x=960, y=0, width=960, height=1080 - 33))

    def test_update_no_valid_monitors(self):
        """UsableRegion: Empty list of monitors doesn't raise exception"""
        UsableRegion().set_monitors([])

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
            test_region.set_monitors([(0, 0, 1280, 1024)])  # type: ignore

        test_region = UsableRegion()
        with self.assertRaises(TypeError):
            # Must be a *list* of StrutPartials
            test_region.set_panels(
                StrutPartial(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12))

        test_region = UsableRegion()
        with self.assertRaises(TypeError):
            # Use a tuple as a test because, just because it's a namedtuple
            # doesn't mean we want *any* tuple with the right arity
            test_region.set_panels([
                (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12)])  # type: ignore

    def test_update_nonempty(self):
        """UsableRegion: only add non-empty entries to _usable"""

        mon1 = Rectangle(1280, 0, 1280, 1024)
        test_region = UsableRegion()
        test_region.set_monitors([mon1,
            Rectangle(0, 0, 100, 0),
            Rectangle(0, 0, 0, 100),
            Rectangle(0, 0, 0, 0)])

        # pylint: disable=protected-access
        self.assertEqual(list(test_region._monitors),
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
