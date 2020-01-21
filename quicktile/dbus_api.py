"""D-Bus API for controlling QuickTile"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

# Silence PyLint about my grouped imports
# pylint: disable=wrong-import-order

import logging

from dbus.service import BusName, Object, method
from dbus import SessionBus
from dbus.exceptions import DBusException
from dbus.mainloop.glib import DBusGMainLoop

# -- Type-Annotation Imports --
from typing import Optional, Tuple
from .commands import CommandRegistry
from .wm import WindowManager
# --


class QuickTile(Object):
    """D-Bus endpoint definition

    :param bus: The connection on which to export this object.
        See the :class:`dbus.service.Object` documentation for details.
    """
    def __init__(self,
            bus: SessionBus,
            commands: CommandRegistry,
            winman: WindowManager) -> None:
        Object.__init__(self, bus, '/com/ssokolow/QuickTile')
        self.commands = commands
        self.winman = winman

    @method(dbus_interface='com.ssokolow.QuickTile',
            in_signature='s', out_signature='b')
    def doCommand(self, command):  # type: (str) -> bool
        """Execute a QuickTile tiling command

        .. todo:: Fix :any:`CommandRegistry.call` so our :any:`bool` return
            isn't always :any:`False`.
        .. todo:: Expose a proper, introspectable D-Bus API.
        .. todo:: When I'm willing to break the external API, retire the
            :meth:`doCommand` name.
        """
        return self.commands.call(command, self.winman)


def init(commands: CommandRegistry,
         winman: WindowManager,
         ) -> Optional[Tuple[BusName, QuickTile]]:
    """Initialize the DBus backend

    This handles hooking D-Bus into the Glib main loop, connecting to the
    session bus, and creating a :class:`QuickTile` instance."""
    try:
        DBusGMainLoop(set_as_default=True)
        sess_bus = SessionBus()
    except DBusException:
        logging.warning("Could not connect to the D-Bus Session Bus.")
        return None

    dbus_name = BusName("com.ssokolow.QuickTile", sess_bus)
    dbus_obj = QuickTile(sess_bus, commands, winman)

    return dbus_name, dbus_obj
