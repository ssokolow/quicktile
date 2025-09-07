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

from tests.functional_harness.env_general import background_proc, os_environ
from tests.functional_harness.x_server import x_server

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def icewm_session():
    # TODO: Re-add support for specifying 'Xephyr'
    with x_server(["Xvfb"], {0: '1024x768x24', 1: '800x600x24'}) as env:
        # TODO: Use a custom configuration file for Openbox
        # TODO: Detect once the window manager has started and wait for that
        #       before running the tests.
        # TODO: Proper test windows.
        log.info("Starting test copy of Openbox...")
        with background_proc(['openbox', '--startup', 'zenity --info'], env):
            with os_environ(env):
                wm = WindowManager()

                start = time.time()
                while wm.get_property(wm.x_root.id, '_NET_SUPPORTING_WM_CHECK',
                        Xatom.WINDOW) is None:
                    if time.time() - start > 5:
                        raise Exception("Timed out waiting for window manager")
                    else:
                        time.sleep(0.1)

                yield env


@pytest.mark.parametrize("command", TEST_SCRIPT)
def test_functional(icewm_session, command):
    """Run the old bank of 'commands don't crash' tests"""
    log.info("Testing command: %s", command)
    subprocess.check_call(['./quicktile.sh', '--no-excepthook',
        command], env=icewm_session)  # nosec


# vim: set sw=4 sts=4 expandtab :
