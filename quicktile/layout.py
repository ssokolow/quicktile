"""Layout calculation code"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

import math
from heapq import heappop, heappush

from .util import euclidean_dist, Gravity, Rectangle

# Allow MyPy to work without depending on the `typing` package
# (And silence complaints from only using the imported types in comments)
MYPY = False
if MYPY:
    # pylint: disable=unused-import
    from typing import (Any, Dict, Iterable, Iterator, List, Optional,  # NOQA
                        Sequence, Sized, Tuple, Union)

    # pylint: disable=import-error, no-name-in-module
    from .util import GeomTuple, PercentRectTuple  # NOQA

    Geom = Union[Rectangle, GeomTuple]  # pylint: disable=invalid-name
del MYPY


# TODO: MyPy type annotations
def check_tolerance(distance, monitor_geom, tolerance=0.1):
    """Check whether a distance is within tolerance, adjusted for window size.

    @param distance: An integer value representing a distance in pixels.
    @param monitor_geom: An (x, y, w, h) tuple representing the monitor
        geometry in pixels.
    @param tolerance: A value between 0.0 and 1.0, inclusive, which represents
        a percentage of the monitor size.
    """

    # Take the euclidean distance of the monitor rectangle and convert
    # `distance` into a percentage of it, then test against `tolerance`.
    return float(distance) / math.hypot(*tuple(monitor_geom)[2:4]) < tolerance


# TODO: Rewrite to use Rectangle
def closest_geom_match(needle, haystack):
    # type: (Geom, Sequence[Geom]) -> Tuple[int, int]
    """Find the geometry in C{haystack} that most closely matches C{needle}.

    @return: A tuple of the euclidean distance and index in C{haystack} for the
             best match.
    """
    # Calculate euclidean distances between the window's current geometry
    # and all presets and store them in a min heap.
    euclid_distance = []  # type: List[Tuple[int, int]]
    for haystack_pos, haystack_val in enumerate(haystack):
        distance = euclidean_dist(needle, haystack_val)

        # MyPy disabled until I figure out why the type annotation on
        # euclid_distance doesn't prevent "Cannot infer type argument 1"
        heappush(euclid_distance, (distance, haystack_pos))  # type: ignore

    # to the next configuration. Otherwise, use the first configuration.
    closest_distance, closest_idx = heappop(euclid_distance)
    return closest_distance, closest_idx


def resolve_fractional_geom(fract_geom, monitor_rect):
    # type: (Union[Rectangle, Geom], Rectangle) -> Rectangle
    """Resolve proportional (eg. 0.5) and preserved (None) coordinates.

    @param fract_geom: An (x, y, w, h) tuple with monitor-relative values in
                       the range from 0.0 to 1.0, inclusive, or a C{Rectangle}
                       which will be passed through without modification.
    @param monitor_rect: A C{Rectangle} defining the bounding box of the
                       monitor (or other desired region) within the desktop.
    """
    if isinstance(fract_geom, Rectangle):
        return fract_geom
    else:
        return Rectangle(
            x=fract_geom[0] * monitor_rect.width,
            y=fract_geom[1] * monitor_rect.height,
            width=fract_geom[2] * monitor_rect.width,
            height=fract_geom[3] * monitor_rect.height)


class GravityLayout(object):  # pylint: disable=too-few-public-methods
    """Helper for translating top-left relative dimensions to other corners.

    Used to generate L{commands.cycle_dimensions} presets.

    Expects to operate on decimal percentage values. (0 <= x <= 1)
    """
    #: Possible window alignments relative to the monitor/desktop.
    GRAVITIES = dict((x.lower().replace('_', '-'), getattr(Gravity, x)) for
        x in Gravity.__members__)  # type: Dict[str, Gravity]

    def __init__(self, margin_x=0, margin_y=0):  # type: (int, int) -> None
        """
        @param margin_x: Horizontal margin to apply when calculating window
            positions, as decimal percentage of screen width.
        @param margin_y: Vertical margin to apply when calculating window
            positions, as decimal percentage of screen height.
        """
        self.margin_x = margin_x
        self.margin_y = margin_y

    # pylint: disable=too-many-arguments
    def __call__(self,
                 width,               # type: float
                 height,              # type: float
                 gravity='top-left',  # type: str
                 x=None,              # type: Optional[float]
                 y=None               # type: Optional[float]
                 ):  # type: (...) -> Tuple[float, float, float, float]
        """Return an C{(x, y, w, h)} tuple relative to C{gravity}.

        This function takes and returns percentages, represented as decimals
        in the range 0 <= x <= 1, which can be multiplied by width and height
        values in actual units to produce actual window geometry.

        It can be used in two ways:

          1. If called B{without} C{x} and C{y} values, it will compute a
          geometry tuple which will align a window C{w} wide and C{h} tall
          according to C{geometry}.

          2. If called B{with} C{x} and C{y} values, it will translate a
          geometry tuple which is relative to the top-left corner so that it is
          instead relative to another corner.

        @param width: Desired width
        @param height: Desired height
        @param gravity: Desired window alignment from L{GRAVITIES}
        @param x: Desired horizontal position if not the same as C{gravity}
        @param y: Desired vertical position if not the same as C{gravity}

        @returns: C{(x, y, w, h)}

        @note: All parameters except C{gravity} are decimal values in the range
        C{0 <= x <= 1}.
        """

        x = x or self.GRAVITIES[gravity].value[0]
        y = y or self.GRAVITIES[gravity].value[1]
        offset_x = width * self.GRAVITIES[gravity].value[0]
        offset_y = height * self.GRAVITIES[gravity].value[1]

        # TODO: Check whether this returns pixel values and, if so, switch to
        #       using Rectangle as the return type
        return (round(x - offset_x + self.margin_x, 3),
                round(y - offset_y + self.margin_y, 3),
                round(width - (self.margin_x * 2), 3),
                round(height - (self.margin_y * 2), 3))


def make_winsplit_positions(columns):
    # type: (int) -> Dict[str, List[PercentRectTuple]]
    """Generate the classic WinSplit Revolution tiling presets

    @todo: Figure out how best to put this in the config file.
    """

    # TODO: Plumb GravityLayout.__init__'s arguments into the config file
    gvlay = GravityLayout()
    col_width = 1.0 / columns
    cycle_steps = tuple(round(col_width * x, 3)
                        for x in range(1, columns))

    center_steps = (1.0,) + cycle_steps
    edge_steps = (0.5,) + cycle_steps

    positions = {
        'center': [gvlay(width, 1, 'center') for width in center_steps],
    }

    for grav in ('top', 'bottom'):
        positions[grav] = [gvlay(width, 0.5, grav) for width in center_steps]
    for grav in ('left', 'right'):
        positions[grav] = [gvlay(width, 1, grav) for width in edge_steps]
    for grav in ('top-left', 'top-right', 'bottom-left', 'bottom-right'):
        positions[grav] = [gvlay(width, 0.5, grav) for width in edge_steps]

    return positions
