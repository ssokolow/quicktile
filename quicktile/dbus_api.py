"""D-Bus API for controlling QuickTile"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

import logging

import dbus.service
from dbus import SessionBus
from dbus.exceptions import DBusException
from dbus.mainloop.glib import DBusGMainLoop

class QuickTile(dbus.service.Object):
    """D-Bus endpoint definition"""
    def __init__(self, bus, commands, winman):
        """
        @param bus: The connection on which to export this object.
            See the C{dbus.service.Object} documentation for details.
        """
        dbus.service.Object.__init__(self, bus,
                                     '/com/ssokolow/QuickTile')
        self.commands = commands
        self.winman = winman

    @dbus.service.method(dbus_interface='com.ssokolow.QuickTile',
             in_signature='s', out_signature='b')
    def doCommand(self, command):
        """Execute a QuickTile tiling command

        @todo 1.0.0: Expose a proper, introspectable D-Bus API"""
        return self.commands.call(command, self.winman)

def init(commands, winman):
    """Initialize the DBus backend"""
    try:
        DBusGMainLoop(set_as_default=True)
        sess_bus = SessionBus()
    except DBusException:
        logging.warn("Could not connect to the D-Bus Session Bus.")
        return None, None

    dbus_name = dbus.service.BusName("com.ssokolow.QuickTile", sess_bus)
    dbus_obj = QuickTile(sess_bus, commands, winman)

    return dbus_name, dbus_obj
