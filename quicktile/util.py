"""Helper functions and classes"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

# Silence PyLint being flat-out wrong about MyPy type annotations and
# complaining about my grouped imports
# pylint: disable=unsubscriptable-object,invalid-sequence-index
# pylint: disable=wrong-import-order

import math, sys
from collections import namedtuple
from enum import Enum
from itertools import chain, combinations

import gi
from functools import reduce  # pylint: disable=redefined-builtin
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk

# -- Type-Annotation Imports --
from typing import (Any, Callable, Iterable, Iterator, List, Optional,
                    Sequence, Tuple, Union)

# Only in type comments
from typing import Dict  # NOQA pylint: disable=unused-import

# pylint: disable=C0103
PercentRectTuple = Tuple[float, float, float, float]
GeomTuple = Tuple[int, int, int, int]

# FIXME: Replace */** with a dict so I can be strict here
CommandCB = Callable[..., Any]

# --

# TODO: Re-add log.debug() calls in strategic places


class Gravity(Enum):  # pylint: disable=too-few-public-methods
    """Gravity definitions used by :class:`Rectangle`"""
    TOP_LEFT = (0.0, 0.0)
    TOP = (0.5, 0.0)
    TOP_RIGHT = (1.0, 0.0)
    LEFT = (0.0, 0.5)
    CENTER = (0.5, 0.5)
    RIGHT = (1.0, 0.5)
    BOTTOM_LEFT = (0.0, 1.0)
    BOTTOM = (0.5, 1.0)
    BOTTOM_RIGHT = (1.0, 1.0)


def clamp_idx(idx: int, stop: int, wrap: bool=True) -> int:
    """Ensure a 0-based index is within a given range [0, stop).

    Uses the same half-open range convention as Python slices.

    :param idx: The value to adjust.
    :param stop: The value to ensure ``idx`` is below.
    :param wrap: If :any:`True`, wrap around rather than saturating.

    :returns: The adjusted value.
    """
    if wrap:
        return idx % stop
    else:
        return max(min(idx, stop - 1), 0)


def euclidean_dist(vec1: Iterable, vec2: Iterable) -> float:
    """Calculate the euclidean distance between two points

    :param vec1: The first coordinate point.
    :param vec2: The second coordinate point.
    :returns: The euclidean distance between the two points.

    .. warning:: This uses :func:`zip`. If one coordinate is of a higher
        dimensionality than the other, it will be truncated to match.
    """
    return math.sqrt(sum(
        (coord1 - coord2) ** 2
        for (coord1, coord2)
        in zip(tuple(vec1), tuple(vec2))
    ))


def powerset(iterable: Iterable[Any]) -> Iterator[Sequence[Any]]:
    """Return an iterator over the power set of the given iterable.

    .. doctest::

        >>> list(powerset([1,2,3]))
        [(), (1,), (2,), (3,), (1, 2), (1, 3), (2, 3), (1, 2, 3)]
    """
    i = list(iterable)
    return chain.from_iterable(combinations(i, j) for j in range(len(i) + 1))

# TODO: Narrow down the type signature


def fmt_table(rows: Union[Dict, Iterable[List]],
              headers: Sequence[str],
              group_by: int=None,
              ) -> str:
    """Format a collection as a textual table.

    :param rows: A dict or iterable of lists representing a sequence of rows.
        If a dict is provided, it will be :func:`sorted` using Python's default
        collation behaviour to ensure consistent output.
    :param headers: Header labels for the columns
    :param group_by: Index of the column to group results by.

    .. doctest::

        >>> print(fmt_table([("Foo", "Wun"), ("Bar", "Too")],
        ...                 ("Things", "Numbers")))
        Things Numbers
        ------ -------
         Foo     Wun
         Bar     Too

        >>> print(fmt_table({"Foo": "Wun", "Bar": "Too"},
        ...                 ("Things", "Numbers")))
        Things Numbers
        ------ -------
         Bar     Too
         Foo     Wun

    .. warning:: This uses :func:`zip` to combine things. The number of columns
        displayed will be defined by the narrowest of all rows.

    .. todo:: Refactor :func:`fmt_table`. Even I don't fully understand what
        my past self wrote by now.
    """
    output = []  # type: List[str]

    # Ensure that, internally, we have a list of lists
    if isinstance(rows, dict):
        # MyPy complains but testing shows this works
        rows = sorted(rows.items())  # type: ignore
    rows = [list(row) for row in rows]

    # Group rows if requested
    groups = {}  # type: Dict[str, List[Any]]
    if group_by is not None:
        headers = list(headers)
        headers.pop(group_by)
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

        result[-1] = result[-1].rstrip()
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

    return ''.join(output).rstrip('\n')

# Internal StrutPartial parent. Exposed so ePyDoc doesn't complain
_StrutPartial = namedtuple('_StrutPartial', 'left right top bottom '
        'left_start_y left_end_y right_start_y right_end_y '
        'top_start_x top_end_x bottom_start_x bottom_end_x')


class StrutPartial(_StrutPartial):
    # pylint: disable=line-too-long
    """A simple wrapper for a sequence taken from `_NET_WM_STRUT_PARTIAL`_.
    (or `_NET_WM_STRUT`_ thanks to default parameters)

    Purpose:
    Minimize the chances of screwing up indexing into `_NET_WM_STRUT_PARTIAL`_

    Method:
        - This namedtuple was created by copy-pasting the definition string
          from `_NET_WM_STRUT_PARTIAL`_ and then manually deleting the commas
          from it if necessary.
        - A :meth:`__new__ <object.__new__>` was added to create
          :class:`StrutPartial` instances from `_NET_WM_STRUT`_ data by
          providing default values for the missing fields.

    :param int left: Thickness of the window's panel reservation on the
        desktop's left  edge in pixels.
    :param int right: Thickness of the window's panel reservation on the
        desktop's right  edge in pixels.
    :param int top: Thickness of the window's panel reservation on the
        desktop's top  edge in pixels.
    :param int bottom: Thickness of the window's panel reservation on the
        desktop's bottom edge in pixels.
    :param int left_start=0: Position of the left panel's top edge in pixels.
    :param int left_end=sys.maxsize: Position of the left panel's bottom edge
        in pixels.
    :param int right_start=0: Position of the right panel's top edge in pixels.
    :param int right_end=sys.maxsize: Position of the right panel's bottom edge
        in pixels.
    :param int top_start=0: Position of the top panel's left edge in pixels.
    :param int top_end=sys.maxsize: Position of the top panel's right edge
        in pixels.
    :param int bottom_start=0: Position of the bottom panel's left edge in
        pixels.
    :param int bottom_end=sys.maxsize: Position of the bottom panel's right
        edge in pixels.

    .. _`_NET_WM_STRUT`: https://specifications.freedesktop.org/wm-spec/1.3/ar01s05.html#NETWMSTRUT
    .. _`_NET_WM_STRUT_PARTIAL`: https://specifications.freedesktop.org/wm-spec/1.3/ar01s05.html#NETWMSTRUTPARTIAL
    """  # NOQA
    __slots__ = ()

    def __new__(cls, left, right, top, bottom,  # pylint: disable=R0913
            left_start_y=0, left_end_y=sys.maxsize,
            right_start_y=0, right_end_y=sys.maxsize,
            top_start_x=0, top_end_x=sys.maxsize,
            bottom_start_x=0, bottom_end_x=sys.maxsize):

        return cls.__bases__[0].__new__(cls, left, right, top, bottom,
            left_start_y, left_end_y, right_start_y, right_end_y,
            top_start_x, top_end_x, bottom_start_x, bottom_end_x)

    def as_rects(self, desktop_rect: 'Rectangle') -> 'List[Rectangle]':
        """Resolve self into absolute coordinates relative to ``desktop_rect``

        Note that struts are relative to the bounding box of the whole desktop,
        not the edges of individual screens.

        (ie. if you have two 1280x1024 monitors and a 1920x1080 monitor in a
        row, with all the tops lined up and a 22px panel spanning all of them
        on the bottom, the strut reservations for the 1280x1024 monitors will
        be :code:`22 + (1080 - 1024) = 56px` to account for the dead space
        below the 1024px-tall monitors.)
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
        ) if bool(x)]

# Keep _StrutPartial from showing up in automated documentation
del _StrutPartial

# Internal Rectangle parent. Exposed so ePyDoc doesn't complain
_Rectangle = namedtuple('_Rectangle', 'x y width height')


class Rectangle(_Rectangle):
    """A representation of a rectangle with some useful methods

    Fundamentally, this is a named tuple of the form ``(x, y, width, height)``
    with some extra methods and properties to make it more useful.

    It supports being initialized with any mixture of ``width`` or ``x2`` and
    ``height`` or ``y2``, and the constructor will ensure that the resulting
    width and height are always positive by adjusting ``x`` and ``y``

    However, **one of** ``width`` or ``x2`` and one of ``height`` or ``y2`` is
    required.

    :param int x:
    :param int y:
    :param int width=None:
    :param int height=None:
    :param int x2=None:
    :param int y2=None:
    :raises ValueError: An invalid set of arguments was provided at
        construction. (eg. ``width`` *and* ``x2``)

    .. doctest::

        >>> Rectangle(5, 2, -10, y2=10)
        Rectangle(x=-5, y=2, width=10, height=8)

    .. warning:: Many of the methods on this type assume the correct use of
        :meth:`to_gravity` and :meth:`from_gravity` and may give nonsensical
        answers if given rectangles which do not have top-left gravity.

        External users of this API are advised to contact the author to
        ensure any changes to make it more mistake-proof are made in a
        coordinated fashion.

    .. todo:: Support initializing with ``width`` and ``x2`` or ``height`` and
        ``y2``. (i.e. Make ``x`` and ``y`` optional so hackery with negative
        widths is not required to achieve the same effect.)

    .. todo:: Figure out how to get :code:`__new__` to auto-apidoc properly.
    """
    __slots__ = ()

    # pylint: disable=too-many-arguments
    def __new__(cls, x: int, y: int, width: int=None, height: int=None,
                x2: int=None, y2: int=None):

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

        # MyPy complains but this is thoroughly unit-tested as working
        return cls.__bases__[0].__new__(  # type: ignore
            cls, x, y, width, height)

    @property
    def xy(self) -> Tuple[int, int]:  # pylint: disable=invalid-name
        """Convenience helper to retrieve an ``(x, y)`` tuple"""
        return (self.x, self.y)

    @property
    def x2(self) -> int:  # pylint: disable=invalid-name
        """X coordinate of the bottom-right corner assuming top-left gravity"""
        return int(self.x + self.width)

    @property
    def y2(self) -> int:  # pylint: disable=invalid-name
        """Y coordinate of the bottom-right corner assuming top-left gravity"""
        return int(self.y + self.height)

    def moved_into(self, other: 'Rectangle', clip: bool=True) -> 'Rectangle':
        """Return a new :class:`Rectangle` that does not exceed the bounds of
        `other`

        (i.e. make a copy that has been slid to the nearest position within
        `other` and only resized if it was larger in one dimension)

        .. doctest::

            >>> parent = Rectangle(0, 0, 40, 40)
            >>> Rectangle(10, 10, 10, 10).moved_into(parent)
            Rectangle(x=10, y=10, width=10, height=10)
            >>> Rectangle(50, 10, 10, 10).moved_into(parent)
            Rectangle(x=30, y=10, width=10, height=10)
            >>> Rectangle(50, 10, 50, 10).moved_into(parent)
            Rectangle(x=0, y=10, width=40, height=10)
            >>> Rectangle(50, 10, 50, 10).moved_into(parent, clip=False)
            Rectangle(x=0, y=10, width=50, height=10)

        :param other: The rectangle to move inside
        :param clip: Whether to call :meth:`intersect` before returning to
            ensure that, if ``self`` is larger than ``other`` in either
            dimension, it will be reduced to match.
        :raises TypeError: ``other`` was not a :class:`Rectangle`
        """
        if not isinstance(other, Rectangle):
            raise TypeError("Expected 'Rectangle', got %r", type(other))
        new = self

        # Slide left or right (prefer aligning left edges if too wide)
        if new.x < other.x:
            new = new._replace(x=other.x)
        elif new.x2 > other.x2:
            # TODO: Rework Rectangle so x can be omitted as long as width
            #       and x2 are supplied.
            new = Rectangle(
                x=max(other.x2 - new.width, 0), y=new.y,
                width=new.width, height=new.height)

        # Slide up or down (prefer aligning tops if too tall)
        if new.y < other.y:
            new = new._replace(y=other.y)
        elif new.y2 > other.y2:
            # TODO: Rework Rectangle so y can be omitted as long as height
            #       and y2 are supplied.
            new = Rectangle(
                x=new.x, y=max(other.y2 - new.height, 0),
                width=new.width, height=new.height)

        # Clip to `other` if it was wider/taller
        if clip:
            new = new.intersect(other)

        return new

    def intersect(self, other: 'Rectangle') -> 'Rectangle':
        """The intersection of two rectangles, assuming top-left gravity.

        :raises TypeError: ``other`` was not a :class:`Rectangle`

        .. doctest::

            >>> rect1 = Rectangle(0, 0, 40, 40)
            >>> Rectangle(20, 20, 50, 60).intersect(rect1)
            Rectangle(x=20, y=20, width=20, height=20)

        .. todo:: I forgot to handle the case where the rectangles have no
            overlap for :meth:`intersect`. I'll need to think about the most
            useful interpretation of that condition.
        """
        if not isinstance(other, Rectangle):
            raise TypeError("Can only intersect with Rectangles")

        # pylint: disable=invalid-name
        x1, y1 = max(self.x, other.x), max(self.y, other.y)
        x2, y2 = min(self.x2, other.x2), min(self.y2, other.y2)

        return Rectangle(x1, y1, max(0, x2 - x1), max(0, y2 - y1))

    def subtract(self, other: 'Rectangle') -> 'Rectangle':
        """Subtract a :class:`Rectangle` from this one.

        This is implemented by shrinking the width/height of ``self`` away from
        ``other`` until they no longer overlap.

        When the overlap crosses more than one edge of ``self``, it will be
        shrunk in whichever direction requires less loss of area.

        Whether to chop left/up or right/down is resolved by comparing the
        center point of the intersecting region with the center point of the
        :class:`Rectangle` being subtracted from.

        In the case of ``other`` chopping `self` into two disjoint regions,
        the smaller one will be cut away as if it were covered by ``other``.

        .. doctest::

           >>> panel = Rectangle(0, 0, 20, 600)
           >>> Rectangle(10, 10, 600, 400).subtract(panel)
           Rectangle(x=20, y=10, width=590, height=400)

        .. note:: If there is no overlap, this will take advantage of the
            immutability of tuple subclasses by returning a reference to
            ``self`` without making a copy.

        .. todo:: :meth:`subtract` will misbehave in the unlikely event that a
               panel is thicker than it is long. I'll want to revisit the
               algorithm once I've cleared out more pressing things.
        """
        overlap = self.intersect(other)

        # If there's no overlap, just trust in a tuple's immutability
        if not overlap:
            # My branch test coverage disagrees with MyPy's assessment that
            # this is unreachable. I guess my custom __bool__ confused it.
            return self  # type: ignore

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

    def __bool__(self) -> bool:
        """A rectangle is truthy if it has a nonzero area"""
        return bool(self.width and self.height)

    def __contains__(self, other) -> bool:
        """A Rectangle is ``in`` another if one is *entirely* within the other.

        If ``other`` is not a :class:`Rectangle`, this will always return
        :any:`False`.

        If you need to check for overlap, check whether
        :meth:`intersect` is truthy.

        This assumes top-left gravity.
        """
        if not isinstance(other, Rectangle):
            return False

        # Assume __new__ normalized for non-negative width and height to allow
        # a simple, clean formulation of this test
        return bool((self.x <= other.x <= other.x2 <= self.x2) and
                    (self.y <= other.y <= other.y2 <= self.y2))

    def union(self, other: 'Rectangle') -> 'Rectangle':
        """The bounding box of two rectangles, assuming top-left gravity

        :raises TypeError: ``other`` was not a :class:`Rectangle`

        .. doctest::

            >>> Rectangle(0, 0, 1, 1).union(Rectangle(5, 5, 1, 1))
            Rectangle(x=0, y=0, width=6, height=6)
        """
        if not isinstance(other, Rectangle):
            raise TypeError("Can only intersect with Rectangles")

        # pylint: disable=invalid-name
        x1, y1 = min(self.x, other.x), min(self.y, other.y)
        x2, y2 = max(self.x2, other.x2), max(self.y2, other.y2)

        return Rectangle(x1, y1, max(0, x2 - x1), max(0, y2 - y1))

    def from_relative(self, other_rect: 'Rectangle') -> 'Rectangle':
        """Interpret self as relative to ``other_rect`` and make it absolute.

        (eg. Convert a window position that's relative to a given monitor's
        top-left corner into one that's relative to the desktop as a whole)

        This assumes top-left gravity.

        :param other_rect: The reference frame to which this rectangle's
            x and y coordinates should be interpreted as relative to.
        :returns: An absolute-coordinates version of this rectangle.
        """
        return self._replace(x=self.x + other_rect.x,
                             y=self.y + other_rect.y)

    def to_relative(self, other_rect: 'Rectangle') -> 'Rectangle':
        """Interpret self as absolute and make it relative to ``other_rect``.

        (eg. Convert a window position that's relative to the top-left corner
        of the desktop as a whole into one that's relative to a single monitor)

        This assumes top-left gravity.

        :param other_rect: The reference frame to make this rectangle's
            x and y coordinates relative to.
        :returns: A relative-coordinates version of this rectangle.
        """
        return self._replace(x=self.x - other_rect.x,
                             y=self.y - other_rect.y)

    def to_point(self) -> 'Rectangle':
        """Return a copy of this :class:`Rectangle` with zero width and height.
        """
        return self._replace(width=0, height=0)

    def from_gravity(self, gravity):  # (Gravity) -> Rectangle
        """Treat ``x`` and ``y`` as not referring to top-left corner and
        return a copy of ``self`` with them translated them so they do.

        .. note:: Almost every :class:`Rectangle` method assumes top-left
            gravity, so this should be the first thing done.

        .. note:: This is intended for working in pixel values and will
            round any results to the nearest integer.

        .. todo:: Think about how to refactor :class:`Rectangle` to guard
            against gravity conversion mistakes.
        """
        return self._replace(
            x=int(self.x - (self.width * gravity.value[0])),
            y=int(self.y - (self.height * gravity.value[1]))
        )

    def to_gravity(self, gravity):  # (Gravity) -> Rectangle
        """Reverse the effect of :meth:`from_gravity`

        Less concisely, this will interpret `self`'s ``x`` and ``y`` members as
        referring to the top-left corner of the rectangle and then return a
        copy with them translated to refer to another point.

        .. note:: Almost every :class:`Rectangle` method assumes top-left
            gravity, so this should be the last thing done.

        .. note:: This is intended for working in pixel values and will
            round any results to the nearest integer.
        """
        return self._replace(
            x=int(self.x + (self.width * gravity.value[0])),
            y=int(self.y + (self.height * gravity.value[1]))
        )

    @classmethod
    def from_gdk(cls, gdk_rect):
        """Factory function to convert from a :class:`Gdk.Rectangle`

        This assumes top-left gravity.
        """
        return cls(x=gdk_rect.x, y=gdk_rect.y,
                   width=gdk_rect.width, height=gdk_rect.height)

    def to_gdk(self):
        """Helper to easily create a :class:`Gdk.Rectangle` from a
        :class:`Rectangle`.

        This assumes top-left gravity.
        """
        gdk_rect = Gdk.Rectangle()
        gdk_rect.x = self.x
        gdk_rect.y = self.y
        gdk_rect.width = self.width
        gdk_rect.height = self.height
        return gdk_rect

# Keep _Rectangle from showing up in automated documentation
del _Rectangle


class UsableRegion(object):
    # pylint: disable=line-too-long
    """A representation of the usable portion of a desktop

    (In essence, this calculates per-monitor `_NET_WORKAREA`_ rectangles
    and allows lookup of the correct one for a given target rectangle)

    .. todo:: Support a more versatile API which allows windows to be clamped
        to a non-rectangular usable region.

    .. _`_NET_WORKAREA`: https://specifications.freedesktop.org/wm-spec/1.3/ar01s03.html#idm45126090602128
    """  # NOQA

    def __init__(self):
        self._monitors = []
        self._struts = []

        # NOTE: Invalidated by resolution changes unless watching notify events
        self._usable = {}  # type: Mapping[Rectangle, Rectangle]

    # TODO: Subscribe to monitor hotplugging in the code which calls this
    def set_monitors(self, monitor_rects: Iterable[Rectangle]):
        """Set the list of monitors rectangles from which to calculate usable
        regions"""
        self._monitors = list(monitor_rects)
        self._update()

    # TODO: Subscribe to changes to panel geometry in the code which calls this
    def set_panels(self, panel_struts: Iterable[StrutPartial]):
        """Set the list of desktop struts to excluded from the usable regions
        """
        self._struts = list(panel_struts)
        self._update()

    def _update(self):
        """Check input values and regenerate internal caches

        This is internal code shared by :meth:`set_monitors` and
        :meth:`set_panels`.

        :raises TypeError: The internal list of monitors contains an entry
            that is not a :class:`Rectangle` or the internal list of struts
            contains an entry that is not a :class:`StrutPartial`.

        .. todo:: Disable documenting private members once I've refactored the
            others which currently should be documented.
        """
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

    def find_usable_rect(self,
            rect: Rectangle, fallback: bool=True) -> Optional[Rectangle]:
        """Find the usable :class:`Rectangle` for the monitor containing
        ``rect``

        :param rect: A rectangle (possibly of zero width and height), the
            center of which will be used to identify a corresponding monitor.
        :param fallback: If :any:`True`, fall back to the nearest monitor if
            ``rect``'s center is not within a monitor.

        .. note:: This will necessarily exclude usable space adjacent to short
            panels. A more versatile API is planned.
        """
        window_center = rect.to_gravity(Gravity.CENTER).to_point()
        for monitor in self._usable:
            if window_center in monitor:
                return self._usable[monitor]  # type: ignore

        if fallback and self._usable:
            distances = []
            for monitor in self._usable:
                mon_center = monitor.to_gravity(Gravity.CENTER).to_point()
                distances.append(
                    (euclidean_dist(window_center.xy, mon_center.xy), monitor))

            # Sort by the first tuple field (the euclidean distance)
            distances.sort()
            # Return usable region corresponding to second field (monitor)
            # corresponding to smallest euc. distance.
            return self._usable[distances[0][1]]  # type: ignore

        return None

    def __bool__(self) -> bool:
        """A :class:`UsableRegion` is truthy if it has a non-zero area."""
        return bool(len(self._usable) > 0 and
            all(self._usable.values()))

    def __repr__(self) -> str:
        """Override :any:`repr` to be more useful for debugging.

        .. doctest::

            >>> print(repr(UsableRegion()))
            Region(<Monitors=[], Struts=[]>)
        """
        return "Region(<Monitors={!r}, Struts={!r}>)".format(
            self._monitors, self._struts)


class XInitError(Exception):
    """Raised when something outside our control causes the X11 connection to
       fail.

    .. todo:: Rework the use of this to use
        :code:`raise XInitError(...) from err`.
    """

    def __str__(self):
        """Augment :any:`str` output to clarify that a user should look
        outside QuickTile for the cause."""
        return ("%s\n\t(The cause of this error lies outside of QuickTile)" %
                Exception.__str__(self))

# vim: set sw=4 sts=4 expandtab :
