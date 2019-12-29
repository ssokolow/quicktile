#!/usr/bin/env python3
"""Context manager for setting up and tearing down a test X server"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "MIT"
__docformat__ = "restructuredtext en"

import logging, os, random, shutil, subprocess, tempfile  # nosec
from contextlib import contextmanager
from distutils.spawn import find_executable

from .env_general import env_vars

# Allow MyPy to work without depending on the `typing` package
# (And silence complaints from only using the imported types in comments)
MYPY = False
if MYPY:
    # pylint: disable=unused-import
    from typing import Dict, Generator, List, Tuple  # NOQA
del MYPY

log = logging.getLogger(__name__)


def _init_x_server(argv, verbose=False):
    # type: (List[str], bool) -> Tuple[subprocess.Popen, bytes]
    """Wrapper for starting an X server with the given command line

    :param argv: The command-line to execute
    :type argv: ``list(str)``

    :raises CalledProcessError: The X server exited with an unexpected error
    :returns: The process object for the X server on success or ``None`` if
        ``display_num`` was already in use.
    :rtype: ``(subprocess.Popen, bytes)``
    """

    # Launch the X server
    read_pipe, write_pipe = os.pipe()
    argv += ['-displayfd', str(write_pipe)]

    # pylint: disable=unexpected-keyword-arg,no-member
    if verbose:
        xproc = subprocess.Popen(argv, pass_fds=[write_pipe])  # nosec
    else:
        xproc = subprocess.Popen(argv, pass_fds=[write_pipe],  # nosec
            stderr=subprocess.STDOUT, stdout=subprocess.DEVNULL)

    display = os.read(read_pipe, 128).strip()
    return xproc, display


@contextmanager
def x_server(argv, screens):
    # type: (List[str], Dict[int, str])-> Generator[Dict[str, str], None, None]
    """Context manager to launch and then clean up an X server.

    argv
        The command to launch the test X server and
        any arguments not relating to defining the attached screens.
    screens
        A ``dict`` mapping screen numbers to
        ``WxHxDEPTH`` strings. (eg. ``{0: '1024x768x32'``})
    """
    # Check for missing requirements
    for cmd in ['xauth', argv[0]]:
        if not find_executable(cmd):
            # pylint: disable=undefined-variable
            raise FileNotFoundError(  # NOQA
                "Cannot find required command {!r}".format(cmd))

    x_server = None
    tempdir = tempfile.mkdtemp()
    try:
        # Because random.getrandbits gets interpreted as a variable length,
        # *ensure* we've got the right number of hex digits
        magic_cookie = b''
        while len(magic_cookie) < 32:
            magic_cookie += hex(random.getrandbits(128))[2:34].encode('ascii')
            magic_cookie = magic_cookie[:32]
        assert len(magic_cookie) == 32, len(magic_cookie)  # nosec
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

        # Initialize an X server on a free display number
        x_server, display_num = _init_x_server(argv + screen_argv)

        # Set up the environment and authorization
        env['DISPLAY'] = ':%s' % display_num.decode('utf8')
        subprocess.check_call(  # nosec
            ['xauth', 'add', env['DISPLAY'], '.', magic_cookie],
            env=env)
        # FIXME: This xauth call once had a random failure. Retry.

        with env_vars(env):
            yield env

    finally:
        if x_server:
            x_server.terminate()
        shutil.rmtree(tempdir)
