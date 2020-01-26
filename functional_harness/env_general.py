"""Assorted context managers for setting up the test environment"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "MIT"

import os, subprocess  # nosec
from contextlib import contextmanager

# Silence PyLint being flat-out wrong about MyPy type annotations
# pylint: disable=unsubscriptable-object

# -- Type-Annotation Imports --
from typing import Any, Dict, Generator  # NOQA


@contextmanager
def background_proc(argv, verbose=False, *args: Any, **kwargs: Any
                    ) -> Generator[None, None, None]:
    """Context manager for scoping the lifetime of a ``subprocess.Popen`` call

    :param argv: The command to be executed
    :param verbose: If :any:`False`, redirect the X server's ``stdout`` and
        ``stderr`` to :file:`/dev/null`
    :param args: Positional arguments to pass to :class:`subprocess.Popen`
    :param kwargs: Keyword arguments to pass to :class:`subprocess.Popen`
    """
    if verbose:
        popen_obj = subprocess.Popen(argv, *args, **kwargs)  # nosec
    else:
        popen_obj = subprocess.Popen(argv,  # type: ignore
            stderr=subprocess.STDOUT, stdout=subprocess.DEVNULL,
            *args, **kwargs)
    try:
        yield
    finally:
        popen_obj.terminate()


@contextmanager
def env_vars(new: Dict[str, str]) -> Generator[None, None, None]:
    """Context manager to temporarily change environment variables

    :param new: Items to be added to :any:`os.environ` for the lifetime of the
        context manager.
    """
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
