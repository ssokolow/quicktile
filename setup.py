#!/usr/bin/env python3
"""

@todo:
 - Identify minimum dependency versions properly.
"""

from __future__ import print_function

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

import io, os, re
from setuptools import setup

try:
    import gi
except ImportError:
    print("WARNING: Could not import PyGI. You will need to it via your "
          "package manager (eg. `sudo apt-get install python3-gi`) before you "
          "will be able to run QuickTile.")
else:
    for name in ['Gdk', 'GdkX11', 'Wnck']:
        try:
            gi.require_version(name, '3.0')
        except ValueError:
            print("WARNING: Could not load the PyGI bindings for %s. You will "
                  "need to install them before you will be able to run "
                  "QuickTile." % name)

# TODO: Switch to PyGI-based D-Bus support

# Get the version from the program rather than duplicating it here
# Source: https://packaging.python.org/en/latest/single_source_version.html


def read(*names, **kwargs):
    """Convenience wrapper for read()ing a file"""
    with io.open(os.path.join(os.path.dirname(__file__), *names),
              encoding=kwargs.get("encoding", "utf8")) as fobj:
        return fobj.read()


def find_version(*file_paths):
    """Extract the value of __version__ from the given file"""
    version_file = read(*file_paths)
    version_match = re.search(r"^__version__\s*=\s*['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")

if __name__ == '__main__':
    setup(
        name='QuickTile',
        version=find_version("quicktile", "version.py"),
        author='Stephan Sokolow (deitarion/SSokolow)',
        author_email='http://ssokolow.com/ContactMe',
        description='Add keyboard-driven window-tiling to any X11 window '
                    'manager (inspired by WinSplit Revolution)',
        long_description=read("README.rst"),
        url="http://ssokolow.com/quicktile/",

        classifiers=[
            'Development Status :: 4 - Beta',
            'Environment :: X11 Applications :: GTK',
            'Intended Audience :: End Users/Desktop',
            'License :: OSI Approved :: GNU General Public License v2 or later'
            ' (GPLv2+)',
            'Natural Language :: English',
            'Operating System :: POSIX',
            'Programming Language :: Python :: 3 :: Only',
            'Topic :: Desktop Environment :: Window Managers',
            'Topic :: Utilities',
        ],
        keywords=('x11 desktop window tiling wm utility addon extension tile '
                  'layout positioning helper keyboard hotkey hotkeys shortcut '
                  'shortcuts tool'),
        license="GPL-2.0+",

        install_requires=['python-xlib'],

        packages=['quicktile'],
        entry_points={
            'console_scripts': ['quicktile=quicktile.__main__:main']
        },
        data_files=[('share/applications', ['quicktile.desktop'])]
    )

# vim: set sw=4 sts=4 expandtab :
