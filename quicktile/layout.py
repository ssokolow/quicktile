"""Layout calculation code"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

import math
from heapq import heappop, heappush

from .util import euclidean_dist, Gravity, Rectangle

# -- Type-Annotation Imports --
from typing import Dict, List, Sequence, Tuple, Union
from .util import GeomTuple, PercentRectTuple

#: MyPy type alias for either `Rectangle` or `GeomTuple`
Geom = Union[Rectangle, GeomTuple]
# --


def check_tolerance(distance: int, monitor_geom: Rectangle,
        tolerance: float=0.1) -> float:
    """Check whether a distance is within a tolerance value calculated as a
        percentage of a monitor's size.

    :param distance: A distance in pixels.
    :param monitor_geom: A ``Rectangle`` representing the monitor geometry.
    :param tolerance: A value between 0.0 and 1.0, inclusive, which represents
        a percentage of the monitor size.

    .. note:: This is not currently in use but is retained for when future
        plans make it necessary to design reliable "invalidate cached data if
        the window was repositioned/resized without QuickTile" code.
    """

    # Take the euclidean distance of the monitor's width and height and convert
    # `distance` into a percentage of it, then test against `tolerance`.
    return (float(distance) /
           math.hypot(monitor_geom.width, monitor_geom.height)
            ) < tolerance


def closest_geom_match(needle: Geom,
        haystack: Sequence[Geom]) -> Tuple[int, int]:
    """Find the geometry in ``haystack`` that most closely matches ``needle``.

    :param needle: The :class:`quicktile.util.Rectangle` or 4-integer tuple to
        search out a match for.
    :param haystack: The set of :class:`quicktile.util.Rectangle` or 4-integer
        tuples to search within.

    :return: A tuple of the euclidean distance and index in ``haystack`` for
        the best match.

    .. note:: This is not currently used by any existing commands. If you are
        using it in your own patched QuickTile versions, please
        `file an issue`_ to prevent the possibility of it being removed.
    .. todo:: Decide whether to get rid of :func:`closest_geom_match`
    .. todo:: If I decide to keep :func:`closest_geom_match`, rewrite it to use
        :class:`quicktile.util.Rectangle`-specific stuff for more readable
        and maintainable code.

    .. _file an issue: https://github.com/ssokolow/quicktile/issues/
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


def resolve_fractional_geom(fract_geom: Union[PercentRectTuple, Rectangle],
        monitor_rect: Rectangle) -> Rectangle:
    """Resolve proportional (eg. ``0.5``) and preserved (``None``) coordinates.

    :param fract_geom: An ``(x, y, w, h)`` tuple containing monitor-relative
        values in the range from 0.0 to 1.0, inclusive, or a
        :class:`quicktile.util.Rectangle` which will be passed through without
        modification.
    :param monitor_rect: A :class:`quicktile.util.Rectangle` defining the
        bounding box of the monitor (or other desired region) within the
        desktop.
    :returns: A rectangle with absolute coordinates derived from
        ``monitor_rect``.
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

    Used to generate :func:`quicktile.commands.cycle_dimensions` presets.

    Expects to operate on decimal percentage values. (0 ≤ x ≤ 1)

    :param margin_x: Horizontal margin to apply when calculating window
        positions, as decimal percentage of screen width.
    :param margin_y: Vertical margin to apply when calculating window
        positions, as decimal percentage of screen height.

    """
    # pylint: disable=no-member
    #: A mapping of possible window alignments relative to the monitor/desktop
    #: as a mapping from formerly manually specified command names to values
    #: the :any:`quicktile.util.Gravity` enum can take on.
    #:
    #: .. todo:: Look into whether I can :any:`GRAVITIES` away entirely.
    GRAVITIES = dict((x.lower().replace('_', '-'), getattr(Gravity, x)) for
        x in Gravity.__members__)  # type: Dict[str, Gravity]

    def __init__(self, margin_x=0, margin_y=0):  # type: (int, int) -> None
        self.margin_x = margin_x
        self.margin_y = margin_y

    # pylint: disable=too-many-arguments
    def __call__(self,
                 width: float,
                 height: float,
                 gravity: str='top-left',
                 x: float=None,
                 y: float=None
                 ) -> PercentRectTuple:
        """Return a relative ``(x, y, w, h)`` tuple relative to ``gravity``.

        This function takes and returns percentages, represented as decimals
        in the range ``0 ≤ x ≤ 1``, which can be multiplied by width and
        height values in actual units to produce actual window geometry.

        It can be used in two ways:

          1. If called **without** ``x`` and ``y`` values, it will compute a
          geometry tuple which will align a window ``w`` wide and ``h`` tall
          according to ``geometry``.

          2. If called **with** ``x`` and ``y`` values, it will translate a
          geometry tuple which is relative to the top-left corner so that it is
          instead relative to another corner.

        :param width: Desired width as a decimal-form percentage
        :param height: Desired height as a decimal-form percentage
        :param gravity: Desired window alignment from :any:`GRAVITIES`
        :param x: Desired horizontal position if not the same as ``gravity``
        :param y: Desired vertical position if not the same as ``gravity``

        :returns: ``(x, y, w, h)`` with all values represented as decimal-form
            percentages.

        .. todo:: Consider writing a percentage-based equivalent to
            :class:`quicktile.util.Rectangle`.
        """

        x = x or self.GRAVITIES[gravity].value[0]
        y = y or self.GRAVITIES[gravity].value[1]
        offset_x = width * self.GRAVITIES[gravity].value[0]
        offset_y = height * self.GRAVITIES[gravity].value[1]

        return (round(x - offset_x + self.margin_x, 3),
                round(y - offset_y + self.margin_y, 3),
                round(width - (self.margin_x * 2), 3),
                round(height - (self.margin_y * 2), 3))


def make_winsplit_positions(columns: int) -> Dict[str, List[PercentRectTuple]]:
    """Generate the classic WinSplit Revolution tiling presets

    :params columns: The number of columns that each tiling preset should be
        built around.
    :return: A dict of presets ready to feed into
        :meth:`quicktile.commands.CommandRegistry.add_many`.

    See :ref:`ColumnCount <ColumnCount>` in the configuration section of the
    manual for further details.

    .. todo:: Plumb :meth:`GravityLayout` arguments into the config
        file and figure out how to generalize func:`make_winsplit_positions`
        into user-customizable stuff as much as possible.
    """

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
