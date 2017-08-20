#!/usr/bin/env python
"""

@todo:
 - Identify minimum dependency versions properly.
 - Figure out how to mark optional packages as optional.
 - Is there a more idiomatic way to handle install_requires for things which
   don't always install the requisite metadata for normal detection?
"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

import io, os, re, sys
from setuptools import setup

# Requirements adapter for packages which may not be PyPI-installable
REQUIRES = ['python-xlib', ]

# Look outside the virtualenv for PyGTK
# Source: https://stackoverflow.com/a/27471354/435253
try:
    import gtk
except ImportError:
    print('--------------')
    import subprocess
    instdir = subprocess.check_output([
        '/usr/bin/python',
        '-c',
        'import os, pygtk; print os.path.dirname(pygtk.__file__)',
    ]).strip()
    for dst_base in sys.path:
        if dst_base.strip():
            break
    for d in [
        'pygtk.pth',
        'pygtk.py',
        'gtk-2.0',
        'gobject',
        'glib',
        'cairo',
        ]:
        src = os.path.join(instdir, d)
        dst = os.path.join(dst_base, d)
        if os.path.exists(src) and not os.path.exists(dst):
            print('linking', d, 'to', dst_base)
            os.symlink(src, dst)

def test_for_imports(choices, package_name, human_package_name):
    """Detect packages without requiring egg metadata

    Fallback to either adding an install_requires entry or exiting with
    an error message.
    """
    if os.environ.get("IS_BUILDING_PACKAGE", None):
        return  # Allow packaging without runtime-only deps installed

    if isinstance(choices, basestring):
        choices = [choices]

    while choices:
        # Detect package without requiring egg metadata
        try:
            current = choices.pop(0)
            __import__(current)
        except ImportError:
            if choices:  # Allow a fallback chain
                continue

            if package_name:
                REQUIRES.append(package_name)
            else:
                print("Could not import '%s'. Please make sure you have %s "
                      "installed." % (current, human_package_name))
                sys.exit(1)

test_for_imports("gtk", "pygtk", "PyGTK")
test_for_imports("dbus", "dbus-python", "python-dbus")

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
        version=find_version("quicktile/__init__.py"),
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
            'Programming Language :: Python :: 2 :: Only',
            'Topic :: Desktop Environment :: Window Managers',
            'Topic :: Utilities',
        ],
        keywords=('x11 desktop window tiling wm utility addon extension tile '
                  'layout positioning helper keyboard hotkey hotkeys shortcut '
                  'shortcuts tool'),
        license="GPL-2.0+",

        install_requires=REQUIRES,

        scripts=['quicktile.py'],
        data_files=[('share/applications', ['quicktile.desktop'])]
    )

# vim: set sw=4 sts=4 expandtab :
