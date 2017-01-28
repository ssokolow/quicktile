#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Unit Test Suite for QuickTile using Nose test discovery"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

import logging, operator, sys
import quicktile

log = logging.getLogger(__name__)

if sys.version_info[0] == 2 and sys.version_info[1] < 7:  # pragma: no cover
    import unittest2 as unittest
else:                                                     # pragma: no cover
    import unittest

#{ Test Mocks
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

#{ Test Cases

class TestHelpers(unittest.TestCase):
    """
    @todo: Figure out how to get the assertEqual readout in bare functions.
    """
    def test_powerset(self):
        """Test that powerset() behaves as expected"""
        src_set = (1, 2, 3)
        expected = [(), (1,), (2,), (3,), (1, 2), (1, 3), (2, 3), (1, 2, 3)]

        for test_set in (tuple(src_set), list(src_set), set(src_set)):
            result = list(quicktile.powerset(test_set))

            # Obvious requirements
            self.assertIn(tuple(), result)
            self.assertIn(tuple(test_set), result)

            # Check that only subsets are returned
            for subset in expected:
                for item in subset:
                    self.assertIn(item, test_set)

            # Check that ALL subsets are returned
            # FIXME: This shouldn't enforce an ordering constraint.
            self.assertEqual(list(quicktile.powerset([1, 2, 3])), expected)

    def test_todo(self):
        self.fail("TODO: Test fmt_table")

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

        self.empty = quicktile.EnumSafeDict()
        self.full = quicktile.EnumSafeDict(
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

    def test_todo(self):
        self.fail("TODO: Implement more tests for EnumSafeDict")
        # TODO: Complete set of tests which try to trick EnumSafeDict into
        #       comparing thing1 and thing2.

class TestCommandRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = quicktile.CommandRegistry()

    def test_todo(self):
        self.fail("TODO: Implement tests for CommandRegistry")

class TestWindowManagerDetached(unittest.TestCase):
    """Tests which exercise L{quicktile.WindowManager} without needing X11."""

    def setUp(self):
        # Shorthand
        self.WM = quicktile.WindowManager  # pylint: disable=invalid-name

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
        self.fail("TODO: Test equivalence of GDK and WNCK constants in "
                "WindowManager.gravities")

    def test_gravity_correctness(self):
        """Gravity Lookup Table: Constants have correct percentage values"""
        self.fail("TODO: Test that each constant in WindowManager.gravities "
                "maps to the correct position on the screen as a value "
                "between 0.0 and 1.0 on the X and Y axis.")

    def test_win_gravity_noop(self):
        """WindowManager.calc_win_gravity: north-west should be a no-op

        (Might as well use the screen shapes to test this. It saves effort.)
        """
        for rect in [self.desktop.get_clipbox()] + self.screens:
            self.assertEqual((rect.x, rect.y),
                self.WM.calc_win_gravity(rect, gtk.gdk.GRAVITY_NORTH_WEST),
                "NORTHWEST gravity should be a no-op.")

    def test_win_gravity_results(self):
        """WindowManager.calc_window_gravity: proper results"""
        self.fail("TODO: Test the output, assuming self.gravities is right")
