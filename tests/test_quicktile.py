# -*- coding: utf-8 -*-
"""Unit Test Suite for QuickTile using Nose test discovery"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

# TODO: I need a functional test to make sure issue #25 doesn't regress

import logging, unittest

# Ensure code coverage counts modules not yet imported by tests.
from quicktile import __main__  # NOQA pylint: disable=unused-import

log = logging.getLogger(__name__)

# class TestCommandRegistry(unittest.TestCase):
#     """Tests for the `CommandRegistry` class"""
#     def setUp(self):  # type: () -> None
#         self.registry = commands.CommandRegistry()
#
#     # TODO: Implement tests for CommandRegistry

# TODO: Implement tests for cycle_dimensions
# TODO: Implement tests for cycle_monitors
# TODO: Implement tests for move_to_position
# TODO: Implement tests for toggle_decorated
# TODO: Implement tests for toggle_desktop
# TODO: Implement tests for toggle_state
# TODO: Implement tests for trigger_keyboard_action
# TODO: Implement tests for workspace_go
# TODO: Implement tests for workspace_send_window

# TODO: Implement tests for KeyBinder

# TODO: Implement tests for QuickTileApp




# vim: set sw=4 sts=4 expandtab :
