"""Helper functions and classes"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

import copy
from collections import MutableMapping, namedtuple
from itertools import chain, combinations

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


class EnumSafeDict(MutableMapping):
    """A dict-like object which avoids comparing objects of different types
    to avoid triggering spurious Glib "comparing different enum types"
    warnings.
    """

    def __init__(self, *args):
        self._contents = {}

        for in_dict in args:
            for key, val in in_dict.items():
                self[key] = val

    def __contains__(self, key):  # type: (Any) -> bool
        ktype = type(key)
        return ktype in self._contents and key in self._contents[ktype]

    def __delitem__(self, key):  # type: (Any) -> None
        if key in self:
            ktype = type(key)
            section = self._contents[ktype]
            del section[key]
            if not section:
                del self._contents[ktype]
        else:
            raise KeyError(key)

    def __getitem__(self, key):  # type: (Any) -> Any
        if key in self:
            return self._contents[type(key)][key]
        else:
            raise KeyError(key)

    def __iter__(self):  # type: () -> Iterator[Any]
        for section in self._contents.values():
            for key in section.keys():
                yield key

    def __len__(self):  # type: () -> int
        return len(self._contents)

    def __repr__(self):  # type: () -> str
        return "%s(%s)" % (self.__class__.__name__,
            ', '.join(repr(x) for x in self._contents.values()))

    def __setitem__(self, key, value):  # type: (Any, Any) -> None
        ktype = type(key)
        self._contents.setdefault(ktype, {})[key] = value

    def iteritems(self):  # TODO: Type signature
        return [(key, self[key]) for key in self]

    def keys(self):  # type: () -> AbstractSet[Any]
        """D.keys() -> list of D's keys"""
        return set(self)


# Internal Rectangle parent. Exposed so ePyDoc doesn't complain
_Rectangle = namedtuple('_Rectangle', 'x y width height')


class Rectangle(_Rectangle):
    """A representation of a rectangle with some useful methods

    (Originally replaces broken Gdk.Rectangle constructor in *buntu 16.04)
    """
    __slots__ = ()

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

        # Swap (x1, y1) and (x2, y2) as appropriate to invert negative sizes
        if width < 0:
            x = x + width
            width = -width
        if height < 0:
            y = y + height
            height = -height

        return cls.__bases__[0].__new__(cls, x, y, width, height)

    @property
    def x2(self):  # type: () -> int
        """X coordinate of the bottom-right corner"""
        return self.x + self.width

    @property
    def y2(self):  # type: () -> int
        """Y coordinate of the bottom-right corner"""
        return self.y + self.height

    def __and__(self, other):  # type: (Rectangle) -> Rectangle
        """The intersection of two rectangles"""
        # TODO: Unit test for this check
        if not isinstance(other, Rectangle):
            return NotImplemented

        # pylint: disable=invalid-name
        x1, y1 = max(self.x, other.x), max(self.y, other.y)
        x2, y2 = min(self.x2, other.x2), min(self.y2, other.y2)

        return Rectangle(x1, y1, max(0, x2 - x1), max(0, y2 - y1))

    def __bool__(self):  # type: () -> bool
        """A rectangle is truthy if it has a nonzero area"""
        return bool(self.width and self.height)

    def __or__(self, other):  # type: (Rectangle) -> Rectangle
        """The bounding box of two rectangles"""
        # TODO: Unit test for this check
        if not isinstance(other, Rectangle):
            return NotImplemented

        # pylint: disable=invalid-name
        x1, y1 = min(self.x, other.x), min(self.y, other.y)
        x2, y2 = max(self.x2, other.x2), max(self.y2, other.y2)

        return Rectangle(x1, y1, max(0, x2 - x1), max(0, y2 - y1))


class Region(object):
    """A replacement for broken cairo.Region constructor in *buntu 16.04"""

    def __init__(self, *initial_rects):
        """Initialze a new region, optionally with a shallow copy of a rect."""
        # TODO: Support taking a Region as an input
        self._rects = copy.deepcopy(list(initial_rects))
        self._clean_up()

    def _clean_up(self):  # type: () -> None
        self._rects.sort()

    def copy(self):  # type: () -> Region
        """Porting shim for things expecting cairo.Region.copy"""
        return copy.deepcopy(self)

    def get_clipbox(self):  # type: () -> Rectangle
        """Return the smallest rectangle which encompasses the region"""
        return Rectangle(*[sum(x) for x in zip(*self._rects)])

    def get_rectangles(self):
        """Retrieve a shallow copy of the internal list of rectangles"""
        return self._rects[:]

    def is_empty(self):
        return len(self._rects) == 0

    def union_with_rect(self, rect):
        """Add a copy of the given Rectangle to this Region"""
        self._rects.append(copy.deepcopy(rect))
        # TODO: Simplify the list of rects
        # (eg. eliminate rects with no areas that don't overlap other rects)
        # (Use https://www.widelands.org/~sirver/wl/141229_devail_rects.pdf)


class XInitError(Exception):
    """Raised when something outside our control causes the X11 connection to
       fail.
    """

    def __str__(self):
        return ("%s\n\t(The cause of this error lies outside of QuickTile)" %
                Exception.__str__(self))

# vim: set sw=4 sts=4 expandtab :
