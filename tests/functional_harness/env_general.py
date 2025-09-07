"""Assorted context managers for setting up the test environment"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "MIT"

import subprocess  # nosec
from contextlib import contextmanager

# Silence PyLint being flat-out wrong about MyPy type annotations
# pylint: disable=unsubscriptable-object

# -- Type-Annotation Imports --
from typing import Any, Generator, Mapping, Union # NOQA


@contextmanager
def background_proc(argv, env: Mapping[str, Union[bytes, str]], verbose=False,
                    *args: Any, **kwargs: Any
                    ) -> Generator[None, None, None]:
    """Context manager for scoping the lifetime of a ``subprocess.Popen`` call

    :param argv: The command to be executed
    :param verbose: If :any:`False`, redirect the X server's ``stdout`` and
        ``stderr`` to :file:`/dev/null`
    :param args: Positional arguments to pass to :class:`subprocess.Popen`
    :param kwargs: Keyword arguments to pass to :class:`subprocess.Popen`
    """
    if verbose:
        popen_obj = subprocess.Popen(  # type: ignore # nosec
            argv, env=env, *args, **kwargs)
    else:
        popen_obj = subprocess.Popen(argv,  # type: ignore # nosec
            stderr=subprocess.STDOUT, stdout=subprocess.DEVNULL,
            env=env, *args, **kwargs)
    try:
        yield popen_obj
    finally:
        popen_obj.terminate()
