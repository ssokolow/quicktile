"""Basic context managers for setting up the test environment"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "MIT"

import os, subprocess  # nosec
from contextlib import contextmanager

# Allow MyPy to work without depending on the `typing` package
# (And silence complaints from only using the imported types in comments)
MYPY = False
if MYPY:
    # pylint: disable=unused-import
    from typing import Any, Dict, Generator  # NOQA
del MYPY


@contextmanager
def background_proc(*args, **kwargs):
    # type: (*Any, **Any) -> Generator[None, None, None]
    """Context manager for scoping the lifetime of a subprocess.Popen call"""
    popen_obj = subprocess.Popen(*args, **kwargs)  # nosec
    try:
        yield
    finally:
        popen_obj.terminate()


@contextmanager
def env_vars(new):
    # type: (Dict[str, str]) -> Generator[None, None, None]
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
