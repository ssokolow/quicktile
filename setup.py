#!/usr/bin/env python
"""

@todo:
 - Decide on a proper way to store the version number in a single place
 - Figure out how to properly handle install_requires for things which don't
   always install the requisite metadata for normal detection.
 - Identify minimum dependency versions properly.
 - Figure out how to mark optional packages as optional.
"""
try:
    from setuptools import setup
    setup # Keep Pyflakes from complaining about redefinition of an "unused".
except ImportError:
    from distutils.core import setup

REQUIRES = ['python-xlib',]

# Detect PyGTK without requiring egg metadata
try:
    import gtk.gdk
    gtk.gdk # Silence PyFlakes warning
except ImportError:
    REQUIRES.append('pygtk')

try:
    import dbus
    dbus
except ImportError:
    REQUIRES.append('dbus-python')

try:
    import quicktile
    version = quicktile.__version__
except:
    version = None

if __name__ == '__main__':
    setup(
        name='QuickTile',
        version=version,
        description='A keyboard-driven window-tiling for X11 desktops (inspired by WinSplit Revolution)',
        author='Stephan Sokolow (deitarion/SSokolow)',
        #author_email='',
        url = "http://ssokolow.com/quicktile/",
        license = "https://www.gnu.org/licenses/gpl-2.0.txt",
        install_requires=REQUIRES,
        scripts = ['quicktile.py'],
        data_files = [
            ('/etc/xdg/autostart', ['quicktile.desktop']),
        ]
    )

