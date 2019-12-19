"""Context manager for setting up and tearing down a test X server"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "MIT"

# Maximum number of seconds to wait for the X server to start before returning
# TODO: Don't just stop blocking and hope it'll be ready in time
STARTUP_TIMEOUT_SECS = 5

# Safety guard against a bug causing infinite looping
MAX_DISPLAY_NUM = 32

import errno, logging, os, random, shutil, subprocess, tempfile, time
from contextlib import contextmanager
from distutils.spawn import find_executable

# Used to detect X server initialization as quickly as possible
import xcffib, xcffib.xproto

from .env_general import env_vars

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

    if (time.time() - started) > STARTUP_TIMEOUT_SECS:
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
        magic_cookie = hex(random.getrandbits(128))[2:34].encode('ascii')
        assert len(magic_cookie) == 32
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
                # TODO: Either don't accept an arbitrary string as input or
                #       default to a value likely to work with other X servers
                #       rather than erroring out.
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
