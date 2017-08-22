"""D-Bus API for controlling QuickTile"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

import logging

from dbus.service import BusName, Object, method
from dbus import SessionBus
from dbus.exceptions import DBusException
from dbus.mainloop.glib import DBusGMainLoop

# Allow MyPy to work without depending on the `typing` package
# (And silence complaints from only using the imported types in comments)
try:
    # pylint: disable=unused-import
    from typing import Optional, Tuple, TYPE_CHECKING  # NOQA

    if TYPE_CHECKING:
        from .commands import CommandRegistry  # NOQA
        from .wm import WindowManager  # NOQA
except:  # pylint: disable=bare-except
    pass

class QuickTile(Object):
    """D-Bus endpoint definition"""
    def __init__(self, bus, commands, winman):
        # type: (SessionBus, CommandRegistry, WindowManager) -> None
        """
        @param bus: The connection on which to export this object.
            See the C{dbus.service.Object} documentation for details.
        """
        Object.__init__(self, bus, '/com/ssokolow/QuickTile')
        self.commands = commands
        self.winman = winman

    @method(dbus_interface='com.ssokolow.QuickTile',
            in_signature='s', out_signature='b')
    def doCommand(self, command):  # type: (str) -> bool
        """Execute a QuickTile tiling command

        @todo 1.0.0: Expose a proper, introspectable D-Bus API"""
        return self.commands.call(command, self.winman)
        # FIXME: self.commands.call always returns None

def init(commands,  # type: CommandRegistry
         winman     # type: WindowManager
         ):  # type: (...) -> Tuple[Optional[BusName], Optional[QuickTile]]
    """Initialize the DBus backend"""
    try:
        DBusGMainLoop(set_as_default=True)
        sess_bus = SessionBus()
    except DBusException:
        logging.warn("Could not connect to the D-Bus Session Bus.")
        return None, None

    dbus_name = BusName("com.ssokolow.QuickTile", sess_bus)
    dbus_obj = QuickTile(sess_bus, commands, winman)

    return dbus_name, dbus_obj
