"""Basic context managers for setting up the test environment"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "MIT"

import os, subprocess
from contextlib import contextmanager

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
