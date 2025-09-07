#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Beginnings of a functional test harness for QuickTile

.. todo:: Don't forget to test unusual configurations such as:

    1. ``monitor-*`` commands with only one monitor
    2. ``workspace-*`` commands with only one workspace
    3. Having screens 1, 2, and 4 but not 0 or 3 (eg. hotplug aftermath)
    4. Having no windows on the desktop
    5. Having no window manager (with and without windows)
    6. Various Xinerama layouts
    7. Test with Xinerama disabled
"""

from __future__ import (absolute_import, division, print_function,
                        with_statement, unicode_literals)

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "MIT"

#: The sequence of commands to call QuickTile with
TEST_SCRIPT = [x.split('#')[0].strip() for x in """
monitor-next-all
monitor-prev-all
monitor-switch-all
monitor-prev-all

monitor-next
monitor-prev
monitor-switch
monitor-prev

bottom
bottom-left
bottom-right
left
center
right
top
top-left
top-right

move-to-bottom
move-to-bottom-left
move-to-bottom-right
move-to-center
move-to-left
move-to-right
move-to-top
move-to-top-left
move-to-top-right

bordered
bordered

always-above
always-above
always-below
always-below
horizontal-maximize
horizontal-maximize
vertical-maximize
vertical-maximize
shade
shade
fullscreen
fullscreen
all-desktops
all-desktops

trigger-move
trigger-resize

workspace-send-down
workspace-go-down

workspace-send-up
workspace-go-up

workspace-send-left
workspace-go-left

workspace-send-right
workspace-go-right

workspace-send-next
workspace-go-next

workspace-send-prev
workspace-go-prev

show-desktop
show-desktop

maximize
maximize

minimize
""".split() if x.split('#')[0].strip()]

import logging, subprocess, time  # nosec

import pytest
from quicktile.wm import WindowManager, Xatom

from tests.functional_harness.env_general import background_proc

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def openbox_session():
    log.info("Starting test copy of Openbox...")
    with background_proc(['openbox', '--startup', 'zenity --info']):
        wm = WindowManager()

        start = time.time()
        while wm.get_property(wm.x_root.id, '_NET_SUPPORTING_WM_CHECK',
                Xatom.WINDOW) is None:
            if time.time() - start > 5:
                raise Exception("Timed out waiting for window manager")
            else:
                time.sleep(0.1)

        yield


@ pytest.mark.parametrize("command", TEST_SCRIPT)
def test_functional(openbox_session, command):
    """Run the old bank of 'commands don't crash' tests"""
    log.info("Testing command: %s", command)
    subprocess.check_call(['./quicktile.sh', '--no-excepthook',
        command], env=openbox_session)  # nosec


def test_quicktile_sh_reports_failure(openbox_session):
    """Verify that quicktile.sh passes the return code through"""
    assert subprocess.call(['./quicktile.sh', '--i-am-an-invalid-option']) == 2

# vim: set sw=4 sts=4 expandtab :
