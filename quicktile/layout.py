"""Layout calculation code"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

# Silence PyLint being flat-out wrong about MyPy type annotations and
# complaining about my grouped imports
# pylint: disable=unsubscriptable-object
# pylint: disable=wrong-import-order

from .util import Gravity, Rectangle

# -- Type-Annotation Imports --
from typing import Dict, List, Union
from .util import GeomTuple, PercentRectTuple

#: MyPy type alias for either `Rectangle` or `GeomTuple`
Geom = Union[Rectangle, GeomTuple]  # pylint: disable=invalid-name
# --


def resolve_fractional_geom(fract_geom: Union[PercentRectTuple, Rectangle],
        monitor_rect: Rectangle) -> Rectangle:
    """Resolve proportional (eg. ``0.5``) coordinates.

    :param fract_geom: An ``(x, y, w, h)`` tuple containing monitor-relative
        values in the range from 0.0 to 1.0, inclusive, or a
        :class:`quicktile.util.Rectangle` which will be passed through without
        modification.
    :param monitor_rect: A :class:`quicktile.util.Rectangle` defining the
        bounding box of the monitor (or other desired region) within the
        desktop.
    :returns: A rectangle with absolute coordinates derived from
        ``monitor_rect``.

    .. doctest::

        >>> resolve_fractional_geom(Rectangle(0, 1, 2, 3),
        ...                         Rectangle(1280, 0, 1280, 1024))
        Rectangle(x=0, y=1, width=2, height=3)
        >>> resolve_fractional_geom((0.5, 0.5, 0.5, 0.5),
        ...                         Rectangle(0, 0, 1280, 1024))
        Rectangle(x=640, y=512, width=640, height=512)
        >>> resolve_fractional_geom((0.5, 0.5, 0.5, 0.5),
        ...                         Rectangle(400, 500, 1280, 1024))
        Rectangle(x=640, y=512, width=640, height=512)
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

    .. doctest::

        >>> layout = GravityLayout()
        >>> layout(0.5, 0.5)
        (0.0, 0.0, 0.5, 0.5)
        >>> layout(0.5, 0.5, 'bottom-right')
        (0.5, 0.5, 0.5, 0.5)
        >>> layout(0.5, 0.5, 'center')
        (0.25, 0.25, 0.5, 0.5)
        >>> layout(0.5, 0.5, x=0.2, y=0.2)
        (0.2, 0.2, 0.5, 0.5)

        >>> layout(0.5, 0.5, 'center', x=0.25, y=0.25)
        (0.0, 0.0, 0.5, 0.5)

        >>> layout = GravityLayout(0.01, 0.02)
        >>> layout(0.5, 0.5)
        (0.01, 0.02, 0.48, 0.46)
        >>> layout(0.5, 0.5, 'bottom-right')
        (0.51, 0.52, 0.48, 0.46)
        >>> layout(0.5, 0.5, 'center')
        (0.26, 0.27, 0.48, 0.46)
        >>> layout(0.5, 0.5, x=0.2, y=0.2)
        (0.21, 0.22, 0.48, 0.46)

        >>> layout(0.5, 0.5, 'center', x=0.25, y=0.25)
        (0.01, 0.02, 0.48, 0.46)
    """
    # pylint: disable=no-member
    #: A mapping of possible window alignments relative to the monitor/desktop
    #: as a mapping from formerly manually specified command names to values
    #: the :any:`quicktile.util.Gravity` enum can take on.
    #:
    #: .. todo:: Look into whether I can factor :any:`GRAVITIES` away entirely.
    GRAVITIES: Dict[str, Gravity] = dict(
        (x.lower().replace('_', '-'), getattr(Gravity, x)) for
        x in Gravity.__members__)

    def __init__(self, margin_x: int = 0, margin_y: int = 0):
        self.margin_x = margin_x
        self.margin_y = margin_y

    # pylint: disable=too-many-arguments
    def __call__(self,
                 width: float,
                 height: float,
                 gravity: str = 'top-left',
                 x: float = None,
                 y: float = None
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
        file and figure out how to generalize :func:`make_winsplit_positions`
        into user-customizable stuff as much as possible.

    .. doctest::

        >>> from pprint import pprint
        >>> pprint(make_winsplit_positions(2)) # doctest: +NORMALIZE_WHITESPACE
        {'bottom': [(0.0, 0.5, 1.0, 0.5), (0.25, 0.5, 0.5, 0.5)],
        'bottom-left': [(0.0, 0.5, 0.5, 0.5), (0.0, 0.5, 0.5, 0.5)],
        'bottom-right': [(0.5, 0.5, 0.5, 0.5), (0.5, 0.5, 0.5, 0.5)],
        'center': [(0.0, 0.0, 1.0, 1), (0.25, 0.0, 0.5, 1)],
        'left': [(0.0, 0.0, 0.5, 1), (0.0, 0.0, 0.5, 1)],
        'right': [(0.5, 0.0, 0.5, 1), (0.5, 0.0, 0.5, 1)],
        'top': [(0.0, 0.0, 1.0, 0.5), (0.25, 0.0, 0.5, 0.5)],
        'top-left': [(0.0, 0.0, 0.5, 0.5), (0.0, 0.0, 0.5, 0.5)],
        'top-right': [(0.5, 0.0, 0.5, 0.5), (0.5, 0.0, 0.5, 0.5)]}
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
