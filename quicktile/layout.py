"""Layout calculation code"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

# Allow MyPy to work without depending on the `typing` package
# (And silence complaints from only using the imported types in comments)
MYPY = False
if MYPY:
    # pylint: disable=unused-import
    from typing import (Any, Dict, Iterable, Iterator, List, Optional,  # NOQA
                        Sequence, Sized, Tuple)

    from .util import PercentRect  # NOQA
del MYPY

class GravityLayout(object):  # pylint: disable=too-few-public-methods
    """Helper for translating top-left relative dimensions to other corners.

    Used to generate L{commands.cycle_dimensions} presets.

    Expects to operate on decimal percentage values. (0 <= x <= 1)
    """
    #: Possible window alignments relative to the monitor/desktop.
    #: @todo 1.0.0: Normalize these to X11 or CSS terminology for 1.0
    #:     (API-breaking change)
    GRAVITIES = {
        'top-left': (0.0, 0.0),
        'top': (0.5, 0.0),
        'top-right': (1.0, 0.0),
        'left': (0.0, 0.5),
        'middle': (0.5, 0.5),
        'right': (1.0, 0.5),
        'bottom-left': (0.0, 1.0),
        'bottom': (0.5, 1.0),
        'bottom-right': (1.0, 1.0),
    }  # type: Dict[str, Tuple[float, float]]

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

        x = x or self.GRAVITIES[gravity][0]
        y = y or self.GRAVITIES[gravity][1]
        offset_x = width * self.GRAVITIES[gravity][0]
        offset_y = height * self.GRAVITIES[gravity][1]

        return (round(x - offset_x + self.margin_x, 3),
                round(y - offset_y + self.margin_y, 3),
                round(width - (self.margin_x * 2), 3),
                round(height - (self.margin_y * 2), 3))

def make_winsplit_positions(columns):
    # type: (int) -> Dict[str, List[PercentRect]]
    """Generate the classic WinSplit Revolution tiling presets

    @todo: Figure out how best to put this in the config file.
    """

    # TODO: Plumb GravityLayout.__init__'s arguments into the config file
    gvlay = GravityLayout()
    col_width = 1.0 / columns
    cycle_steps = tuple(round(col_width * x, 3)
                        for x in range(1, columns))

    middle_steps = (1.0,) + cycle_steps
    edge_steps = tuple(sorted(set((0.5,) + cycle_steps)))

    positions = {
        'middle': [gvlay(width, 1, 'middle') for width in middle_steps],
    }

    for grav in ('top', 'bottom'):
        positions[grav] = [gvlay(width, 0.5, grav) for width in middle_steps]
    for grav in ('left', 'right'):
        positions[grav] = [gvlay(width, 1, grav) for width in edge_steps]
    for grav in ('top-left', 'top-right', 'bottom-left', 'bottom-right'):
        positions[grav] = [gvlay(width, 0.5, grav) for width in edge_steps]

    return positions
