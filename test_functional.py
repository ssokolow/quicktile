#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Beginnings of a functional test harness for QuickTile

.. todo:: Don't forget to test unusual configurations such as:

    1. monitor-* commands with only one monitor
    2. workspace-* commands with only one workspace
    3. Having screens 1, 2, and 4 but not 0 or 3 (eg. hotplug aftermath)
    4. Having no windows on the desktop
    5. Having no window manager (with and without windows)
    6. Various Xinerama layouts
"""

from __future__ import (absolute_import, division, print_function,
                        with_statement, unicode_literals)

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "MIT"

#: The sequence of commands to call QuickTile with
TEST_SCRIPT = """
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

maximize
maximize
minimize

trigger-move
trigger-resize

show-desktop
show-desktop

workspace-send-down
workspace-send-up
workspace-send-left
workspace-send-right
workspace-send-next
workspace-send-prev

workspace-go-down
workspace-go-up
workspace-go-left
workspace-go-right
workspace-go-next
workspace-go-prev
"""

import logging, shlex, subprocess  # nosec

from functional_harness.env_general import background_proc
from functional_harness.x_server import x_server

log = logging.getLogger(__name__)


def run_tests():
    """Run the old bank of 'commands don't crash' tests"""
    lines = [x.split('#')[0].strip() for x in TEST_SCRIPT.split('\n')]
    lines = [x for x in lines if x]
    for pos, command in enumerate(lines):
        log.info("Testing command %d of %d: %s", pos + 1, len(lines), command)
        subprocess.check_call(['./quicktile.sh', command])  # nosec


def main():
    """The main entry point, compatible with setuptools entry points."""
    from argparse import ArgumentParser, RawDescriptionHelpFormatter
    parser = ArgumentParser(formatter_class=RawDescriptionHelpFormatter,
            description='Functional test runner for QuickTile',
            epilog="NOTE: Running tests under the Xephyr X server will change "
            "their behaviour if they depend on Xvfb's ability to present "
            "a desktop with non-sequentially numbered screens.")
    parser.add_argument('-v', '--verbose', action="count",
        default=2, help="Increase the verbosity. Use twice for extra effect.")
    parser.add_argument('-q', '--quiet', action="count",
        default=0, help="Decrease the verbosity. Use twice for extra effect.")
    parser.add_argument('-X', '--x-server', default="Xvfb", metavar="CMD",
        help="The X server to launch for testing (Try 'Xephyr' to debug tests "
             "using a live view. The default is '%(default)s'.)")
    # Reminder: %(default)s can be used in help strings.

    args = parser.parse_args()

    # Set up clean logging to stderr
    log_levels = [logging.CRITICAL, logging.ERROR, logging.WARNING,
                  logging.INFO, logging.DEBUG]
    args.verbose = min(args.verbose - args.quiet, len(log_levels) - 1)
    args.verbose = max(args.verbose, 0)
    logging.basicConfig(level=log_levels[args.verbose],
                        format='%(levelname)s: %(message)s')

    log.warning("This does not currently check the results of the tiling "
        "operations it requests. As such, it serves only as a way to check "
        "for uncaught exceptions being raised in code that isn't yet "
        "unit tested.")
    log.warning("TODO: Inject a test window into the nested X session so "
        "non-windowless commands don't bail out in the common code.")
    with x_server(shlex.split(args.x_server), {0: '1024x768x24'}):
        run_tests()

if __name__ == '__main__':
    main()

# vim: set sw=4 sts=4 expandtab :
