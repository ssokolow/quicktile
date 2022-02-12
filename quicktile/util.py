"""Helper functions and classes"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

# Silence PyLint being flat-out wrong about MyPy type annotations and
# complaining about my grouped imports
# pylint: disable=unsubscriptable-object,invalid-sequence-index
# pylint: disable=wrong-import-order

import math, sys
from collections import namedtuple
from enum import Enum, IntEnum, unique
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


@unique
class Edge(IntEnum):
    """Constants used by :meth:`StrutPartial.as_rects` to communicate
    information :class:`UsableRegion` needs to properly handle panel
    reservations on interior edges.

    The values of the enum's members correspond to the tuple indexes in
    StrutPartial.
    """
    LEFT = 1
    RIGHT = 2
    TOP = 3
    BOTTOM = 4


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


def clamp_idx(idx: int, stop: int, wrap: bool = True) -> int:
    """Ensure a 0-based index is within a given range [0, stop).

    Uses the same half-open range convention as Python slices.

    :param idx: The value to adjust.
    :param stop: The value to ensure ``idx`` is below.
    :param wrap: If :any:`True`, wrap around rather than saturating.

    :returns: The adjusted value.
    """
    if wrap:
        return idx % stop
    return max(min(idx, stop - 1), 0)


def euclidean_dist(vec1: Iterable, vec2: Iterable) -> float:
    """Calculate the `euclidean distance`_ between two points

    :param vec1: The first coordinate point.
    :param vec2: The second coordinate point.
    :returns: The euclidean distance between the two points.

    .. warning:: This uses :func:`zip`. If one coordinate is of a higher
        dimensionality than the other, it will be silently truncated to match.

    .. todo:: Consider explicitly supporting :class:`Rectangle` so this can
        cleanly take two rectangles and compare their centers without
        boilerplate.

    .. _euclidean distance: https://en.wikipedia.org/wiki/Euclidean_distance
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
              group_by: int = None,
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
        displayed will be defined by the row with the fewest columns.

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

    def __new__(cls, left=0, right=0, top=0, bottom=0,  # pylint: disable=R0913
            left_start_y=0, left_end_y=sys.maxsize,
            right_start_y=0, right_end_y=sys.maxsize,
            top_start_x=0, top_end_x=sys.maxsize,
            bottom_start_x=0, bottom_end_x=sys.maxsize):

        return cls.__bases__[0].__new__(cls, left, right, top, bottom,
            left_start_y, left_end_y, right_start_y, right_end_y,
            top_start_x, top_end_x, bottom_start_x, bottom_end_x)

    def as_rects(self, desktop_rect: 'Rectangle'
                 ) -> 'List[Tuple[Edge, Rectangle]]':
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
            (Edge.LEFT, Rectangle(
                x=desktop_rect.x,
                y=self.left_start_y,
                width=self.left,
                y2=self.left_end_y).intersect(desktop_rect)),
            # Right
            (Edge.RIGHT, Rectangle(
                x=desktop_rect.x2,
                y=self.right_start_y,
                width=-self.right,
                y2=self.right_end_y).intersect(desktop_rect)),
            # Top
            (Edge.TOP, Rectangle(
                x=self.top_start_x,
                y=desktop_rect.y,
                x2=self.top_end_x,
                height=self.top).intersect(desktop_rect)),
            # Bottom
            (Edge.BOTTOM, Rectangle(
                x=self.bottom_start_x,
                y=desktop_rect.y2,
                x2=self.bottom_end_x,
                height=-self.bottom).intersect(desktop_rect)),
        ) if bool(x[1])]


# Keep _StrutPartial from showing up in automated documentation
del _StrutPartial

# Internal Rectangle parent. Exposed so ePyDoc doesn't complain
_Rectangle = namedtuple('_Rectangle', 'x y width height')


class Rectangle(_Rectangle):
    """A representation of a rectangle with some useful methods

    Fundamentally, this is a named tuple of the form ``(x, y, width, height)``
    with some extra methods and properties to make it more useful.

    It supports being initialized with any mixture of ``x``, ``width``, or
    ``x2`` and ``y``, ``height`` or ``y2`` as long as sufficient information
    is provided to define a rectangle, and the constructor will ensure that the
    resulting width and height are always positive by adjusting ``x`` and ``y``

    :param int x=None:
    :param int y=None:
    :param int width=None:
    :param int height=None:
    :param int x2=None:
    :param int y2=None:
    :raises ValueError: An invalid set of arguments was provided at
        construction. (eg. ``width`` *and* ``x2``)

    .. doctest::

        >>> Rectangle(5, 2, -10, y2=10)
        Rectangle(x=-5, y=2, width=10, height=8)
        >>> Rectangle(x2=10, y2=12, width=5, height=6)
        Rectangle(x=5, y=6, width=5, height=6)
        >>> Rectangle(x2=10, y2=12, width=-5, height=-6)
        Rectangle(x=10, y=12, width=5, height=6)

    .. warning:: Many of the methods on this type assume the correct use of
        :meth:`to_gravity` and :meth:`from_gravity` and may give nonsensical
        answers if given rectangles which do not have top-left gravity.

        External users of this API are advised to contact the author to
        ensure any changes to make it more mistake-proof are made in a
        coordinated fashion.

    .. todo:: Figure out how to get :code:`__new__` to auto-apidoc properly.
    """
    __slots__ = ()

    # pylint: disable=too-many-arguments
    def __new__(cls, x: int = None, y: int = None,
                width: int = None, height: int = None,
                x2: int = None, y2: int = None):

        # -- Check for a valid combination of arguments --
        if (x, width, x2).count(None) != 1:
            raise ValueError("Exactly one of x, width, or x2 must be None")
        if (y, height, y2).count(None) != 1:
            raise ValueError("Exactly one of y, height, or y2 must be None")

        # -- Ensure we have all parameters present --
        if x is not None and x2 is not None:
            width = x2 - x
        elif x2 is not None and width is not None:
            x = x2 - width
        elif x is not None and width is not None:
            x2 = x + width
        else:
            raise Exception("Unreachable")  # pragma: nocover

        if y is not None and y2 is not None:
            height = y2 - y
        elif y2 is not None and height is not None:
            y = y2 - height
        elif y is not None and height is not None:
            y2 = y + height
        else:
            raise Exception("Unreachable")  # pragma: nocover

        # Swap (x1, y1) and (x2, y2) as appropriate to invert negative sizes
        if width < 0:
            x, x2 = x2, x
            width = abs(width)
        if height < 0:
            y, y2 = y2, y
            height = abs(height)

        # Ensure values are integers, and that width and height are
        # not None beyond this point
        x, y, width, height = int(x), int(y), int(width), int(height)

        # MyPy complains but this is thoroughly unit-tested as working
        return cls.__bases__[0].__new__(  # type: ignore
            cls, x, y, width, height)

    # TODO: Automated tests
    def __mul__(self, factor: Union[int, float]) -> 'Rectangle':
        """Return a new Rectangle with all dimensions multiplied by ``factor``

        This is used to apply scaling factors to monitor rectangles returned by
        GDK so they'll be in the device pixel coordinates that the Wnck APIs
        expect.

        .. doctest::

            >>> Rectangle(320, 240, 640, 480) * 2
            Rectangle(x=640, y=480, width=1280, height=960)
            >>> Rectangle(320, 240, 640, 480) * 0.5
            Rectangle(x=160, y=120, width=320, height=240)
        """
        return self._replace(
            x=int(self.x * factor),
            y=int(self.y * factor),
            width=int(self.width * factor),
            height=int(self.height * factor))

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

    @property
    def area(self) -> int:
        """Convenience helper for calculating area of the rectangle"""
        return int(self.width * self.height)

    def closest_of(self, candidates: 'List[Rectangle]') -> 'Rectangle':
        """Find and return the rectangle that ``self`` is closest to.

        (Unified definition of how to resolve edge cases in various operations
        in the most intuitive way possible.)

        Based on empirical testing, the following definition of closeness has
        been chosen:

        1. Choose the rectangle with the largest area area of
           overlap. (``self.intersect(candidate).area``)
        2. To break ties (eg. all motions result in no overlap), choose the
           motion with the shortest :func:`euclidean_dist` between the two
           rectangles' centers.

        (Using the center points is important when considering operations which
        both move and resize a rectangle.)

        :param candidates: Rectangles to consider for closeness.

        .. todo:: Refactor the tests so they don't only test :meth:`closest_of`
           indirectly and don't engage in needless duplication.
        """
        choices = []
        for candidate in candidates:
            overlap = candidate.intersect(self)

            p_self = self.to_gravity(Gravity.CENTER).to_point()
            p_candidate = candidate.to_gravity(Gravity.CENTER).to_point()
            euc_dist = euclidean_dist(p_self.xy, p_candidate.xy)

            choices.append((overlap.area, -euc_dist, candidate))

        # Return choice with largest overlap, breaking ties with the smallest
        # euclidean distance
        return max(choices)[-1]

    def moved_into(self, other: 'Rectangle') -> 'Rectangle':
        """Attempt to return a new :class:`Rectangle` of the same width and
        height that does not exceed the bounds of `other`.

        If ``self`` is wider/taller than ``other``, line up the left/top edge
        as appropriate and allow the rest to overflow right/down-ward.

        It is your responsibility to call :meth:`intersect` afterward if you
        would like to clip the rectangle to fit.

        .. doctest::

            >>> parent = Rectangle(0, 0, 40, 40)
            >>> Rectangle(10, 10, 10, 10).moved_into(parent)
            Rectangle(x=10, y=10, width=10, height=10)
            >>> Rectangle(50, 10, 10, 10).moved_into(parent)
            Rectangle(x=30, y=10, width=10, height=10)
            >>> Rectangle(50, 10, 50, 10).moved_into(parent)
            Rectangle(x=0, y=10, width=50, height=10)
            >>> Rectangle(50, 10, 10, 50).moved_into(parent)
            Rectangle(x=30, y=0, width=10, height=50)

        :param other: The rectangle to move inside
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

        return new

    def moved_off_of(self, other: 'Rectangle') -> 'Rectangle':
        """Return a copy of ``self`` that has been moved as little as possible
        such that it no longer overlaps ``other``.

        This will move the rectangle either horizontally or vertically but not
        both and will rely on :meth:`closest_of` to choose a direction.

        .. doctest::

           >>> panel = Rectangle(0, 0, 20, 600)
           >>> Rectangle(10, 10, 600, 400).moved_off_of(panel)
           Rectangle(x=20, y=10, width=600, height=400)

        .. note:: If no change is needed, this will take advantage of the
            immutability of tuple subclasses by returning a reference to
            ``self`` without making a copy.

        .. warning:: This has no conception of "inside/outside the desktop"
            and may shove a window out of bounds if you don't first ensure that
            it's mostly on the correct side of a panel using something like
            :meth:`moved_into`.

        .. todo:: Decide whether it's worth it to add support for some kind of
            ``constrain_within`` or ``preferred_direction`` argument to
            :meth:`moved_off_of`.
        """
        # If there's no overlap, just trust in a tuple's immutability
        if not self.intersect(other):
            return self

        return self.closest_of([
            Rectangle(  # Push left
                y=self.y, width=self.width, height=self.height, x2=other.x),
            Rectangle(  # Push right
                y=self.y, width=self.width, height=self.height, x=other.x2),
            Rectangle(  # Push up
                x=self.x, width=self.width, height=self.height, y2=other.y),
            Rectangle(  # Push down
                x=self.x, width=self.width, height=self.height, y=other.y2),
        ])

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
        """Return a copy of ``self`` which has been shrunk along one axis
        such that it no longer overlaps ``other``.

        The edge to cut away is determined by calling :meth:`moved_off_of` and
        then :meth:`intersect`-ing ``self`` with the result.

        (In effect, it will generate candidate rectangles for all four possible
        directions and then use :meth:`closest_of` to choose the one that
        results in the smallest change.)

        .. doctest::

           >>> panel = Rectangle(0, 0, 20, 600)
           >>> Rectangle(10, 10, 600, 400).subtract(panel)
           Rectangle(x=20, y=10, width=590, height=400)

        .. note:: If there is no overlap, this will take advantage of the
            immutability of tuple subclasses by returning a reference to
            ``self`` without making a copy.

        .. warning:: This has no conception of "inside/outside the desktop"
            and may make it entirely out-of-bounds rather than entirely
            in-bounds if you don't first ensure that the target rectangle is
            more in-bounds than out-of-bounds.

        .. todo:: Decide whether it's worth it to add support for some kind of
            ``constrain_within`` or ``preferred_direction`` argument to
            :meth:`subtract`.
        """
        result = self.intersect(self.moved_off_of(other))

        return result if result != self else self

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
        """Assuming top-left gravity, return the smallest rectangle that both
        ``self`` and ``other`` fit inside. (ie. the bounding box)

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
    """A representation of the usable portion of a desktop

    This stores a set of monitors and a set of :class:`StrutPartial` instances
    and can be used to clip or move window rectangles to fit within the usable
    space.
    """

    def __init__(self):
        self._monitors_raw = []  # type: List[Rectangle]
        self._monitors = []  # type: List[Rectangle]
        self._struts = []    # type: List[StrutPartial]
        self._strut_rects = []  # type: List[Rectangle]

    # TODO: Subscribe to monitor hotplugging in the code which calls this
    def set_monitors(self, monitor_rects: Iterable[Rectangle]):
        """Set the list of monitor rectangles from which to calculate usable
        regions"""
        self._monitors_raw = list(monitor_rects)
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
        for rect in self._monitors_raw:
            if not isinstance(rect, Rectangle):
                raise TypeError("monitors must be of type Rectangle")
        for strut in self._struts:
            if not isinstance(strut, StrutPartial):
                raise TypeError("struts must be of type StrutPartial")
                # ...so they can be re-calculated on resolution change

        # Exclude monitors with zero area
        self._monitors = [x for x in self._monitors_raw if x]

        # Calculate the desktop rectangle (and ensure it extends to (0, 0))
        desktop_rect = reduce(lambda x, y: x.union(y), self._monitors,
            Rectangle(0, 0, 0, 0))

        # Resolve the struts to Rectangles relative to desktop_rect
        strut_rects = []  # type: List[Rectangle]
        for strut in self._struts:
            # TODO: Test for off-by-one bugs
            # TODO: Think of a more efficient way to do this
            for strut_pair in strut.as_rects(desktop_rect):
                strut_rects.append(self._trim_strut(strut_pair))
        self._strut_rects = strut_rects

    def _trim_strut(self, strut: Tuple[Edge, Rectangle]) -> Rectangle:
        """Trim a strut rectangle to just the monitor it applies to

        This is internal code used by :meth:`_update` but split out to manage
        complexity and improve testability.

        .. doctest::

            >>> region = UsableRegion()
            >>> region.set_monitors([Rectangle(0, 0, 1280, 1024),
            ...                      Rectangle(1280, 0, 1280, 1024),
            ...                      Rectangle(0, 1024, 1280, 1024),
            ...                      Rectangle(1280, 1024, 1280, 1024)])
            >>> region._trim_strut((Edge.LEFT, Rectangle(0, 0, 1304, 1024)))
            Rectangle(x=1280, y=0, width=24, height=1024)
            >>> region._trim_strut((Edge.RIGHT, Rectangle(1256, 0, 1304, 800)))
            Rectangle(x=1256, y=0, width=24, height=800)
            >>> region._trim_strut((Edge.TOP, Rectangle(0, 0, 1280, 1048)))
            Rectangle(x=0, y=1024, width=1280, height=24)
            >>> region._trim_strut((Edge.BOTTOM, Rectangle(0, 1000, 80, 1048)))
            Rectangle(x=0, y=1000, width=80, height=24)
        """
        edge, strut_rect = strut

        for monitor in self._monitors:
            overlap = monitor.intersect(strut_rect)
            if not bool(overlap):
                continue

            # Gotta do this manually unless I decide to add support for
            # subtract taking a directional hint so it doesn't chop off the
            # wrong end.
            if overlap.width == monitor.width:
                if edge == Edge.LEFT:
                    strut_rect = Rectangle(x=monitor.x2, y=strut_rect.y,
                        width=strut_rect.x2 - monitor.x2,
                        height=strut_rect.height
                                           )
                elif edge == Edge.RIGHT:
                    strut_rect = Rectangle(x=strut_rect.x, y=strut_rect.y,
                        width=monitor.x - strut_rect.x,
                        height=strut_rect.height
                                           )
            if overlap.height == monitor.height:
                if edge == Edge.TOP:
                    strut_rect = Rectangle(x=strut_rect.x, y=monitor.y2,
                        width=strut_rect.width,
                        height=strut_rect.y2 - monitor.y2,
                                           )
                elif edge == Edge.BOTTOM:
                    strut_rect = Rectangle(x=strut_rect.x, y=strut_rect.y,
                        height=monitor.y - strut_rect.y,
                        width=strut_rect.width
                                           )

        return strut_rect

    def clip_to_usable_region(self, rect: Rectangle) -> Optional[Rectangle]:
        """Given a rectangle, return a copy that has been shrunk to fit inside
        the usable region of the monitor.

        This is defined as a rectangle that:

        1. Does not extend outside the monitor
        2. Does not overlap any panels

        The output rectangle will not extend outside the bounds of the input
        rectangle.

        See :meth:`Rectangle.subtract` for more information on how corner
        overlaps between windows and panels are resolved.

        :param rect: A rectangle representing desired window geometry that
            should be shrunk to not overlap any panels or None if there was
            no overlap.
        """
        monitor = self.find_monitor_for(rect)
        if not monitor:
            return None

        rect = rect.intersect(monitor)
        for panel in self._strut_rects:
            rect = rect.subtract(panel)

        # Apparently MyPy can't see through custom __bool__ implementations
        return rect or None  # type: ignore

    def move_to_usable_region(self, rect: Rectangle) -> Optional[Rectangle]:
        """Given a rectangle, return a copy that has been moved to be entirely
        within the nearest monitor and to not overlap any panels."""

        monitor = self.find_monitor_for(rect)
        if not monitor:
            return None

        rect = rect.moved_into(monitor)
        for panel in self._strut_rects:
            rect = rect.moved_off_of(panel)

        return rect

    def find_monitor_for(self, rect: Rectangle) -> Optional[Rectangle]:
        """Find the **full** (including space reserved for panels)
        :class:`Rectangle` for the monitor containing ``rect`` using
        :meth:`Rectangle.closest_of`.

        :param rect: A rectangle (possibly of zero width and height),
            representing a point of reference for the monitor search.
        """
        if self._monitors:
            return rect.closest_of(self._monitors)

        return None

    def __bool__(self) -> bool:
        """A :class:`UsableRegion` is truthy if it has at least one monitor
        with nonzero area.

        .. todo:: Is it worth it to also verify that panel reservations have
           not eaten up the entirety of a monitor in :meth:`__bool__`?
        """
        return bool(len(self._monitors) > 0 and
            all(self._monitors))

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
        outside QuickTile for the cause.


        .. code-block:: text

            XInitError: Hello, I am your usual exception message
                (The cause of this error lies outside of QuickTile)
        """
        return ("%s\n\t(The cause of this error lies outside of QuickTile)" %
                Exception.__str__(self))

# vim: set sw=4 sts=4 expandtab :
