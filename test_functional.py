#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""Beginnings of a functional test harness for QuickTile

This script replicates some of the algorithms implemented in the unattributed
/usr/bin/xvfb-run script included in the xvfb package provided by
Ubuntu Linux 14.04.5 LTS.

It is my belief that the commonalities between these two scripts are inherent
to the process of implementing an algorithm which satisfies the requirements
and, thus, not meeting the criteria to be eligible for protection under
copyright law.

TODO: Don't forget to test unusual configurations such as:
    1. Having screens 1, 2, and 4 but not 0 or 3 (eg. hotplug aftermath)
    2. Having no windows on the desktop
    3. Having no window manager (with and without windows)
    4. Various Xinerama layouts
"""

from __future__ import (absolute_import, division, print_function,
                        with_statement, unicode_literals)

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "MIT"

MAX_DISPLAY_NUM = 32  # Safety guard against a bug causing infinite looping
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
middle
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

import errno, logging, os, random, shlex, shutil, subprocess, tempfile, time
from contextlib import contextmanager
from distutils.spawn import find_executable

# Used to detect X server initialization as quickly as possible
import xcffib, xcffib.xproto


log = logging.getLogger(__name__)

def _init_x_server(argv, display_num, magic_cookie, verbose=False):
    """Wrapper for starting an X server with the given command line

    (Workaround for inherently racy nature of finding a free display number)

    @param argv: The command-line to execute
    @param display_num: The X11 display number to try to claim
    @type argv: C{list(str)}
    @type display_num: C{int}

    @raises CalledProcessError: The X server exited with an unexpected error
    @returns: The process object for the X server on success or C{None} if
        C{display_num} was already in use.
    @rtype: C{subprocess.Popen} or C{None}

    @todo: With SIGUSR1 not working in my tests as a way to detect that the
           server is ready to accept connections, how do I protect against
           race conditions where another test running in parallel might grab
           the display number in between my checking for the lockfile and
           running the X server?

           It's not feasible to wait long enough to be probabilistically sure
           that the X server has had time to either succeed or die.
    """
    # Detect in-use displays and bail out early so our test won't get a false
    # positive by successfully connecting to the wrong X server.
    lock_path = '/tmp/.X%d-lock' % display_num
    if os.path.exists(lock_path):
        log.debug("Display number already taken: %d", display_num)
        return None

    # Launch the X server
    argv += [':%d' % display_num]
    if verbose:
        xproc = subprocess.Popen(argv)
    else:
        with open(os.devnull, 'w') as devnull:
            xproc = subprocess.Popen(argv,
                                     stderr=subprocess.STDOUT, stdout=devnull)

    # Wait for the process to die, start accepting connections, or for
    # 5 seconds to pass
    # TODO: Refactor to be cleaner
    started = time.time()
    while xproc.poll() is None and (time.time() - started < 5):
        try:
            conn = xcffib.connect(display=':%d' % display_num,
                                  auth=b'MIT-MAGIC-COOKIE-1:' + magic_cookie)
        except xcffib.ConnectionException:
            time.sleep(0.1)  # Limit spinning when the server is slow to start
            continue
        else:
            if not xproc.poll():
                conn.disconnect()
                log.debug("X server on :%d accepting connections", display_num)
                return xproc

    if (time.time() - started) > 5:
        log.warning("Timed out while waiting for X server")
        if xproc.poll() is None:
            return xproc

    if xproc.returncode == 1 and os.path.exists(lock_path):
        log.debug("Race condition on display number %d", display_num)
        return None
    else:
        log.critical('Failed to call %s: exit code %s', argv, xproc.returncode)
        raise subprocess.CalledProcessError(xproc.returncode, repr(argv), '')

@contextmanager
def background_proc(*args, **kwargs):
    """Context manager for scoping the lifetime of a subprocess.Popen call"""
    popen_obj = subprocess.Popen(*args, **kwargs)
    try:
        yield
    finally:
        popen_obj.terminate()

@contextmanager
def env_vars(new):
    """Context manager to temporarily change environment variables"""
    old_vals = {}
    try:
        for key, val in new.items():
            if key in os.environ:
                old_vals[key] = os.environ[key]
            os.environ[key] = val

        yield
    finally:
        for key, val in old_vals.items():
            os.environ[key] = val

@contextmanager
def x_server(argv, screens):
    """Context manager to launch and then clean up an X server.

    @param argv: The command to launch the test X server and any arguments
        not relating to defining the attached screens.
    @param screens: A dict mapping screen numbers to WxHxDEPTH strings.
        (eg. C{{0: '1024x768x32'}})
    @type argv: C{list(str)}
    @type screens: C{dict((int, str))}

    #raises OSError: This function will synthesize a "too many open files"
        error (C{OSError(errno.EMFile, ...)}) if it hits C{MAX_DISPLAY_NUM}
        before it finds a usable X11 display number.
    """
    # Check for missing requirements
    for cmd in ['xauth', argv[0]]:
        if not find_executable(cmd):
            raise OSError(errno.ENOENT,
                          "Cannot find required command '%s'" % [cmd])

    x_server = None
    tempdir = tempfile.mkdtemp()
    try:
        magic_cookie = hex(random.getrandbits(128))[2:-1]
        xauthfile = os.path.join(tempdir, 'Xauthority')
        env = {'XAUTHORITY': xauthfile}

        open(xauthfile, 'w').close()  # create empty file

        # Convert `screens` into the format Xorg servers expect
        screen_argv = []
        for screen_num, screen_geom in screens.items():
            if 'Xvfb' in argv[0]:
                screen_argv.extend(['-screen', '%d' % screen_num, screen_geom])
            elif 'Xephyr' in argv[0]:
                screen_argv.extend(['-screen', screen_geom])
            else:
                # TODO: Decide on a better way to handle this
                raise ValueError("Unrecognized X server. Cannot infer format "
                                 "for specifying screen geometry.")

        # Try to initialize an X server on a free display number
        for display_num in range(0, MAX_DISPLAY_NUM + 1):
            x_server = _init_x_server(argv + screen_argv,
                                      display_num, magic_cookie)
            if x_server:
                # Set up the environment and authorization
                env['DISPLAY'] = ':%d' % display_num
                subprocess.check_call(
                    ['xauth', 'add', env['DISPLAY'], '.', magic_cookie],
                    env=env)
                # FIXME: This xauth call once had a random failure. Retry.

                # Yield to be contents of the `with` block and then break
                # to start the teardown and cleanup process
                with env_vars(env):
                    yield env
                break
        else:
            # Raise a "too many open files" if we can't find an open DISPLAY
            # (As a reasonably intuitive approximation. Mention in docstring.)
            raise OSError(errno.EMFILE,
                          "Failed to find a free X11 display number")

    finally:
        if x_server:
            x_server.terminate()
        shutil.rmtree(tempdir)

def run_tests():
    """Run the old bank of 'commands don't crash' tests"""
    lines = [x.split('#')[0].strip() for x in TEST_SCRIPT.split('\n')]
    lines = [x for x in lines if x]
    for pos, command in enumerate(lines):
        log.info("Testing command %d of %d: %s", pos + 1, len(lines), command)
        subprocess.check_call(['quicktile', command])

def main():
    """The main entry point, compatible with setuptools entry points."""
    # If we're running on Python 2, take responsibility for preventing
    # output from causing UnicodeEncodeErrors. (Done here so it should only
    # happen when not being imported by some other program.)
    import sys
    if sys.version_info.major < 3:
        reload(sys)
        sys.setdefaultencoding('utf-8')  # pylint: disable=no-member

    from argparse import ArgumentParser, RawDescriptionHelpFormatter
    parser = ArgumentParser(formatter_class=RawDescriptionHelpFormatter,
            description=__doc__.replace('\r\n', '\n').split('\n--snip--\n')[0])
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

    with x_server(shlex.split(args.x_server), {0: '1024x768x24'}):
        run_tests()

if __name__ == '__main__':
    main()

# vim: set sw=4 sts=4 expandtab :
