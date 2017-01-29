#!/usr/bin/env python
"""

@todo:
 - Decide on a proper way to store the version number in a single place
 - Figure out how to properly handle install_requires for things which don't
   always install the requisite metadata for normal detection.
 - Identify minimum dependency versions properly.
 - Figure out how to mark optional packages as optional.
"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

REQUIRES = ['python-xlib', ]

# Detect PyGTK without requiring egg metadata
try:
    # pylint: disable=unused-import
    import gtk.gdk  # NOQA
except ImportError:
    REQUIRES.append('pygtk')

try:
    # pylint: disable=unused-import
    import dbus  # NOQA
except ImportError:
    REQUIRES.append('dbus-python')

try:
    # TODO: Replace this with the technique used by lgogd_uri
    import quicktile
    version = quicktile.__version__
except Exception:  # pylint: disable=broad-except
    version = None

if __name__ == '__main__':
    setup(
        name='QuickTile',
        version=version,
        description='A keyboard-driven window-tiling for X11 desktops '
                    '(inspired by WinSplit Revolution)',
        author='Stephan Sokolow (deitarion/SSokolow)',
        author_email='http://ssokolow.com/ContactMe',
        url="http://ssokolow.com/quicktile/",
        license="https://www.gnu.org/licenses/gpl-2.0.txt",
        install_requires=REQUIRES,
        scripts=['quicktile.py'],
        data_files=[
            ('/etc/xdg/autostart', ['quicktile.desktop']),
        ]
    )

# vim: set sw=4 sts=4 expandtab :
