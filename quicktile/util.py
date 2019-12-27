"""Helper functions and classes"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

import sys
from collections import namedtuple
from enum import Enum
from itertools import chain, combinations

import gi
from functools import reduce  # pylint: disable=redefined-builtin
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk

# Allow MyPy to work without depending on the `typing` package
# (And silence complaints from only using the imported types in comments)
#
# TODO: Just import typing normally once I no longer need to remain compatible
#       with ePyDoc.
MYPY = False
if MYPY:  # pragma: nocover
    # pylint: disable=unused-import
    from typing import (AbstractSet, Any, Callable, Dict, Iterable,  # NOQA
                        Iterator, List, Optional, Sequence, Tuple, Union)

    # pylint: disable=C0103
    PercentRectTuple = Tuple[float, float, float, float]
    GeomTuple = Tuple[int, int, int, int]

    # FIXME: Replace */** with a dict so I can be strict here
    CommandCB = Callable[..., Any]
del MYPY

# TODO: Re-add log.debug() calls in strategic places


class Gravity(Enum):  # pylint: disable=too-few-public-methods
    """Gravity definitions used by Rectangle"""
    TOP_LEFT = (0.0, 0.0)
    TOP = (0.5, 0.0)
    TOP_RIGHT = (1.0, 0.0)
    LEFT = (0.0, 0.5)
    CENTER = (0.5, 0.5)
    RIGHT = (1.0, 0.5)
    BOTTOM_LEFT = (0.0, 1.0)
    BOTTOM = (0.5, 1.0)
    BOTTOM_RIGHT = (1.0, 1.0)


def clamp_idx(idx, stop, wrap=True):
    # type: (int, int, bool) -> int
    """Ensure a 0-based index is within a given range [0, stop).

    Uses the same half-open range convention as Python slices.

    @param wrap: If C{True}, wrap around rather than saturating.
    """
    if wrap:
        return idx % stop
    else:
        return max(min(idx, stop - 1), 0)


def powerset(iterable):  # type: (Iterable[Any]) -> Iterator[Sequence[Any]]
    """C{powerset([1,2,3])} --> C{() (1,) (2,) (3,) (1,2) (1,3) (2,3) (1,2,3)}

    @rtype: iterable
    """
    i = list(iterable)
    return chain.from_iterable(combinations(i, j) for j in range(len(i) + 1))


def fmt_table(rows,          # type: Any
              headers,       # type: Sequence
              group_by=None  # type: Optional[int]
              ):  # type: (...) -> str
    """Format a collection as a textual table.

    @param headers: Header labels for the columns
    @param group_by: Index of the column to group results by.
    @type rows: C{dict} or iterable of iterables
    @type headers: C{list(str)}
    @type group_by: C{int}

    @attention: This uses C{zip()} to combine things. The number of columns
        displayed will be defined by the narrowest of all rows.

    @rtype: C{str}
    """
    output = []  # type: List[str]

    if isinstance(rows, dict):
        rows = list(sorted(rows.items()))

    groups = {}  # type: Dict[str, List[str]]
    if group_by is not None:
        headers = list(headers)
        headers.pop(group_by)
        rows = [list(row) for row in rows]
        for row in rows:
            group = row.pop(group_by)
            groups.setdefault(group, []).append(row)
    else:
        groups[''] = rows

    # Identify how much space needs to be allocated for each column
    col_maxlens = []
    for pos, header in enumerate(headers):
        maxlen = max(len(x[pos]) for x in rows if len(x) > pos)
        col_maxlens.append(max(maxlen, len(header)))

    def fmt_row(row, pad=' ', indent=0, min_width=0):  # TODO: Type signature
        """Format a fmt_table row"""
        result = []
        for width, label in zip(col_maxlens, row):
            result.append('%s%s ' % (' ' * indent, label.ljust(width, pad)))

        _width = sum(len(x) for x in result)
        if _width < min_width:
            result[-1] = result[-1][:-1]
            result.append(pad * (min_width - _width + 1))

        result.append('\n')
        return result

    # Print the headers and divider
    group_width = max(len(x) for x in groups)
    output.extend(fmt_row(headers))
    output.extend(fmt_row([''] * len(headers), '-', min_width=group_width + 1))

    for group in sorted(groups):
        if group:
            output.append("\n%s\n" % group)
        for row in groups[group]:
            output.extend(fmt_row(row, indent=1))

    return ''.join(output)

# Internal StrutPartial parent. Exposed so ePyDoc doesn't complain
_StrutPartial = namedtuple('StrutPartial', 'left right top bottom '
        'left_start_y left_end_y right_start_y right_end_y '
        'top_start_x top_end_x bottom_start_x bottom_end_x')


class StrutPartial(_StrutPartial):
    """A simple wrapper for the sequence retrieved from _NET_WM_STRUT_PARTIAL.
    (or _NET_WM_STRUT thanks to default parameters)

    Purpose:
    Minimize the chances of screwing up indexing into _NET_WM_STRUT_PARTIAL

    Method:
        - This namedtuple was created by copy-pasting the definition string
          from https://specifications.freedesktop.org/wm-spec/1.3/ar01s05.html
          and then manually deleting the commas from it if necessary.
        - A __new__ was added to create StrutPartial instances from
          _NET_WM_STRUT data by providing default values for the missing fields
    """
    __slots__ = ()

    def __new__(cls, left, right, top, bottom,  # pylint: disable=R0913
            left_start_y=0, left_end_y=sys.maxsize,
            right_start_y=0, right_end_y=sys.maxsize,
            top_start_x=0, top_end_x=sys.maxsize,
            bottom_start_x=0, bottom_end_x=sys.maxsize):

        return cls.__bases__[0].__new__(cls, left, right, top, bottom,
            left_start_y, left_end_y, right_start_y, right_end_y,
            top_start_x, top_end_x, bottom_start_x, bottom_end_x)

    def as_rects(self, desktop_rect):  # type: (Rectangle) -> List[Rectangle]
        """Resolve self into absolute coordinates relative to desktop_rect

        Note that struts are relative to bounding box of the whole desktop,
        not the edges of individual screens.

        (ie. if you have two 1280x1024 monitors and a 1920x1080 monitor in a
        row, with all the tops lined up and a 22px panel spanning all of them
        on the bottom, the strut reservations for the 1280x1024 monitors will
        be 22 + (1080 - 1024) = 56px to account for the dead space below the
        1024px-tall monitors too.)
        """
        return [x for x in (
            # Left
            Rectangle(
                x=desktop_rect.x,
                y=self.left_start_y,
                width=self.left,
                y2=self.left_end_y).intersect(desktop_rect),
            # Right
            Rectangle(
                x=desktop_rect.x2,
                y=self.right_start_y,
                width=-self.right,
                y2=self.right_end_y).intersect(desktop_rect),
            # Top
            Rectangle(
                x=self.top_start_x,
                y=desktop_rect.y,
                x2=self.top_end_x,
                height=self.top).intersect(desktop_rect),
            # Bottom
            Rectangle(
                x=self.bottom_start_x,
                y=desktop_rect.y2,
                x2=self.bottom_end_x,
                height=-self.bottom).intersect(desktop_rect),
        ) if x]


# Internal Rectangle parent. Exposed so ePyDoc doesn't complain
_Rectangle = namedtuple('_Rectangle', 'x y width height')


class Rectangle(_Rectangle):
    """A representation of a rectangle with some useful methods"""
    __slots__ = ()

    # pylint: disable=too-many-arguments
    def __new__(cls, x, y, width=None, height=None, x2=None, y2=None):
        # Validate that we got a correct number of arguments
        if (width, x2).count(None) != 1:
            raise ValueError("Either width or x2 must be None and not both")
        if (height, y2).count(None) != 1:
            raise ValueError("Either height or y2 must be None and not both")

        # If given a rectangle in two-point form, convert to width/height form
        if x2:
            width = x2 - x
        if y2:
            height = y2 - y

        # Ensure values are integers, and that width and height are
        # not None beyond this point
        x, y, width, height = int(x), int(y), int(width or 0), int(height or 0)

        # Swap (x1, y1) and (x2, y2) as appropriate to invert negative sizes
        if width < 0:
            x = x + width
            width = abs(width)
        if height < 0:
            y = y + height
            height = abs(height)

        return cls.__bases__[0].__new__(cls, x, y, width, height)

    @property
    def x2(self):  # pylint: disable=invalid-name
        # type: () -> int
        """X coordinate of the bottom-right corner assuming top-left gravity"""
        return self.x + self.width

    @property
    def y2(self):  # pylint: disable=invalid-name
        # type: () -> int
        """Y coordinate of the bottom-right corner assuming top-left gravity"""
        return self.y + self.height

    def intersect(self, other):  # type: (Rectangle) -> Rectangle
        """The intersection of two rectangles, assuming top-left gravity."""
        if not isinstance(other, Rectangle):
            raise TypeError("Can only intersect with Rectangles")

        # pylint: disable=invalid-name
        x1, y1 = max(self.x, other.x), max(self.y, other.y)
        x2, y2 = min(self.x2, other.x2), min(self.y2, other.y2)

        return Rectangle(x1, y1, max(0, x2 - x1), max(0, y2 - y1))

    def subtract(self, other):
        """Subtract a rectangle from this one.

        This is implemented by shrinking the width/height of `self` away from
        `other` until they no longer overlap.

        When the overlap crosses more than one edge of `self`, it will be
        shrunk in whichever direction requires less loss of area.

        Whether to chop left/up or right/down is resolved by comparing the
        center point of the intersecting region with the center point of the
        Rectangle being subtracted from.

        In the case of `other` chopping `self` into two disjoint regions,
        the smaller one will be cut away as if it were covered by `other`.

        @note: If there is no overlap, this will return a reference to `self`
               without making a copy.

        @todo: This will misbehave in the unlikely event that a panel is
               thicker than it is long. I'll want to revisit the algorithm
               once I've cleared out more pressing things.
        """
        overlap = self.intersect(other)

        # If there's no overlap, just trust in a tuple's immutability
        if not overlap:
            return self

        # Compare centers as the least insane way to handle the possibility of
        # one Rectangle splitting the other in half when we don't want to
        # support returning multiple rectangles at this time.
        self_center = self.to_gravity(Gravity.CENTER).to_point()
        overlap_center = overlap.to_gravity(Gravity.CENTER).to_point()

        if overlap.width < overlap.height:  # If we're shrinking left/right
            new_width = self.width - overlap.width
            if overlap_center.x < self_center.x:  # `other` is left of center
                return self._replace(x=other.x2, width=new_width)
            else:
                return self._replace(width=new_width)
        else:  # If we're shrinking up/down
            new_height = self.height - overlap.height
            if overlap_center.y < self_center.y:
                return self._replace(y=other.y2, height=new_height)
            else:
                return self._replace(height=new_height)

    def __bool__(self):  # type: () -> bool
        """A rectangle is truthy if it has a nonzero area"""
        return bool(self.width and self.height)

    def __contains__(self, other):
        """A Rectangle is `in` another if one is *entirely* within the other.

        If you need to check for overlap, check whether
        C{self.intersect(other)} is truthy.

        @note: This assumes top-left gravity.
        """
        if not isinstance(other, Rectangle):
            return False

        # Assume __new__ normalized for non-negative width and height to allow
        # a simple, clean formulation of this test
        return ((self.x <= other.x <= other.x2 <= self.x2) and
                (self.y <= other.y <= other.y2 <= self.y2))

    def union(self, other):  # type: (Rectangle) -> Rectangle
        """The bounding box of two rectangles, assuming top-left gravity"""
        if not isinstance(other, Rectangle):
            raise TypeError("Can only intersect with Rectangles")

        # pylint: disable=invalid-name
        x1, y1 = min(self.x, other.x), min(self.y, other.y)
        x2, y2 = max(self.x2, other.x2), max(self.y2, other.y2)

        return Rectangle(x1, y1, max(0, x2 - x1), max(0, y2 - y1))

    def from_relative(self, other_rect):
        # type: (Rectangle) -> Rectangle
        """Interpret self as relative to other_rect and make it absolute

        (eg. Convert a window position that's relative to a given monitor's
        top-left corner into one that's relative to the desktop as a whole)

        @note: This assumes top-left gravity.
        """
        return self._replace(x=self.x + other_rect.x,
                             y=self.y + other_rect.y)

    def to_relative(self, other_rect):
        # type: (Rectangle) -> Rectangle
        """Interpret self as absolute and make it relative to other_rect

        (eg. Convert a window position that's relative to the top-left corner
        of the desktop as a whole into one that's relative to a single monitor)

        @note: This assumes top-left gravity.
        """
        return self._replace(x=self.x - other_rect.x,
                             y=self.y - other_rect.y)

    def to_point(self):
        # type: () -> Rectangle
        """Return a new Rectangle with zero width and height"""
        return self._replace(width=0, height=0)

    def from_gravity(self, gravity):  # (Gravity) -> Rectangle
        """Treat x and y as not referring to top-left corner and translate

        @note: Almost every C{Rectangle} method assumes top-left gravity, so
               this should be the first thing done.

        @todo: Think about how to refactor to guard against that error.
        """
        return self._replace(
            x=int(self.x - (self.width * gravity.value[0])),
            y=int(self.y - (self.height * gravity.value[1]))
        )

    def to_gravity(self, gravity):  # (Gravity) -> Rectangle
        """Reverse the effect of from_gravity

        Less concisely, this will interpret `self`'s `x` and `y` members as
        referring to the top-left corner of the rectangle and then translate
        them to refer to another point.

        @note: Almost every C{Rectangle} method assumes top-left gravity, so
               this should be the last thing done.

        @note: This is intended for working in pixel values and will truncate
               any decimal component.
        """
        return self._replace(
            x=int(self.x + (self.width * gravity.value[0])),
            y=int(self.y + (self.height * gravity.value[1]))
        )

    @classmethod
    def from_gdk(cls, gdk_rect):
        """Factory function to convert from a Gdk.Rectangle

        @note: This assumes top-left gravity.
        """
        return cls(x=gdk_rect.x, y=gdk_rect.y,
                   width=gdk_rect.width, height=gdk_rect.height)

    def to_gdk(self):
        """Helper to easily create a Gdk.Rectangle from a Rectangle

        @note: This assumes top-left gravity.
        """
        gdk_rect = Gdk.Rectangle()
        gdk_rect.x = self.x
        gdk_rect.y = self.y
        gdk_rect.width = self.width
        gdk_rect.height = self.height
        return gdk_rect


class UsableRegion(object):
    """A representation of the usable portion of a desktop

    (In essence, this calculates per-monitor _NET_WORKAREA rectangles
    and allows lookup of the correct one for a given target rectangle)
    """

    def __init__(self):
        self._monitors = []
        self._struts = []

        # NOTE: Invalidated by resolution changes unless watching notify events
        self._usable = {}  # type: Mapping[Rectangle, Rectangle]

    # TODO: Subscribe to monitor hotplugging in the code which calls this
    def set_monitors(self, monitor_rects):
        # type: (Iterable[Rectangle]) -> None
        """Set the list of monitors from which to calculate usable regions"""
        self._monitors = list(monitor_rects)
        self._update()

    # TODO: Subscribe to changes to panel geometry in the code which calls this
    def set_panels(self, panel_struts):
        # type: (Iterable[StrutPartial]) -> None
        """Set the list of rectangles to be excluded from the usable regions"""
        self._struts = list(panel_struts)
        self._update()

    def _update(self):  # type: () -> None
        """Check input values and regenerate internal caches"""
        # Assert that all monitors are Rectangles
        # and all Struts are StrutPartials
        for rect in self._monitors:
            if not isinstance(rect, Rectangle):
                raise TypeError("monitors must be of type Rectangle")
        for strut in self._struts:
            if not isinstance(strut, StrutPartial):
                raise TypeError("struts must be of type StrutPartial")
                # ...so they can be re-calculated on resolution change

        # Calculate the desktop rectangle (and ensure it extends to (0, 0))
        desktop_rect = reduce(lambda x, y: x.union(y), self._monitors)
        desktop_rect = desktop_rect.union(Rectangle(0, 0, 0, 0))

        # Resolve the struts to Rectangles relative to desktop_rect
        strut_rects = []  # type: List[Rectangle]
        for strut in self._struts:
            # TODO: Test for off-by-one bugs
            strut_rects.extend(strut.as_rects(desktop_rect))

        # Calculate the *usable* monitor regions by subtracting the strut rects
        self._usable = {}
        for monitor in self._monitors:
            usable = monitor
            for panel in strut_rects:
                usable = usable.subtract(panel)

            # Only add non-empty entries to _usable
            if usable:
                self._usable[monitor] = usable

    def find_usable_rect(self, rect):
        # type: (Rectangle) -> Optional[Rectangle]
        """Find the usable Rectangle for the monitor containing rect"""
        window_center = rect.to_gravity(Gravity.CENTER).to_point()
        for monitor in self._usable:
            if window_center in monitor:
                return self._usable[monitor]
        return None

    def __bool__(self):  # type: () -> bool
        """A Region is truthy if it has a non-zero area"""
        return bool(len(self._usable) > 0 and
            all(self._usable.values()))

    def __repr__(self):  # type: () -> str
        return "Region(<Monitors={!r}, Struts={!r}>)".format(
            self._monitors, self._struts)


class XInitError(Exception):
    """Raised when something outside our control causes the X11 connection to
       fail.
    """
    # TODO: Rework the use of this to use `raise XInitError(...) from err`

    def __str__(self):
        return ("%s\n\t(The cause of this error lies outside of QuickTile)" %
                Exception.__str__(self))

# vim: set sw=4 sts=4 expandtab :
