#!/usr/bin/env python3
"""Wrapper for easily setting up and tearing down a test X server"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "MIT"

# Silence PyLint being flat-out wrong about MyPy type annotations
# complaining about my grouped imports
# pylint: disable=unsubscriptable-object,invalid-sequence-index
# pylint: disable=wrong-import-order

import logging, os, random, shutil, subprocess, tempfile  # nosec
from contextlib import contextmanager
from distutils.spawn import find_executable

from .env_general import env_vars

# -- Type-Annotation Imports --
from typing import Dict, Generator, List, Tuple

log = logging.getLogger(__name__)


def _init_x_server(argv: List[str], verbose: bool=False
                   ) -> Tuple[subprocess.Popen, bytes]:
    """Wrapper for starting an X server with the given command line

    :param argv: The command-line to execute
    :param verbose: If :any:`False`, redirect the X server's ``stdout`` and
        ``stderr`` to :file:`/dev/null`
    :returns: The process object for the X server.

    :raises subprocess.CalledProcessError: The X server exited with an
        unexpected error.
    """

    # Launch the X server
    read_pipe, write_pipe = os.pipe()
    argv += ['+xinerama', '-displayfd', str(write_pipe)]

    # pylint: disable=unexpected-keyword-arg,no-member
    if verbose:
        xproc = subprocess.Popen(argv, pass_fds=[write_pipe])  # nosec
    else:
        xproc = subprocess.Popen(argv, pass_fds=[write_pipe],  # nosec
            stderr=subprocess.STDOUT, stdout=subprocess.DEVNULL)

    display = os.read(read_pipe, 128).strip()
    return xproc, display


@contextmanager
def x_server(argv: List[str], screens: Dict[int, str]
             ) -> Generator[Dict[str, str], None, None]:
    """Context manager to launch and then clean up an X server.

    :param argv: The command to launch the test X server and
        any arguments not relating to defining the attached screens.
    :param screens: A :any:`dict <dict>` mapping screen numbers to
        ``WxHxDEPTH`` strings. (eg. ``{0: '1024x768x32'}``)

    :raises subprocess.CalledProcessError: The X server or :command:`xauth`
        failed unexpectedly.
    :raises FileNotFoundError: Could not find either the :command:`xauth`
        command or ``argv[0]``.
    :raises PermissionError: Somehow, we lack write permission inside a
        directory created by :func:`tempfile.mkdtemp`.
    :raises ValueError: ``argv[0]`` was not an X server binary we know how to
        specify monitor rectangles for.
        (either :command:`Xvfb` or :command:`Xephyr`)
    :raises UnicodeDecodeError: The X server's ``-displayfd`` option wrote
        a value to the given FD which could not be decoded as UTF-8 when it
        should have been part of the 7-bit ASCII subset of UTF-8.

    .. todo:: Either don't accept an arbitrary ``argv`` string as input to
        :func:`x_server` or default to a behaviour likely to work with other X
        servers rather than erroring out.
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
