#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# pylint: disable=line-too-long,too-many-lines
"""QuickTile, a WinSplit clone for X11 desktops

Thanks to Thomas Vander Stichele for some of the documentation cleanups.

@todo:
 - Reconsider use of C{--daemonize}. That tends to imply self-backgrounding.
 - Look into supporting XPyB (the Python equivalent to C{libxcb}) for global
   keybinding.
 - Clean up the code. It's functional, but an ugly rush-job.
 - Implement the secondary major features of WinSplit Revolution (eg.
   process-shape associations, locking/welding window edges, etc.)
 - Consider rewriting L{commands.cycle_dimensions} to allow command-line use to jump to
   a specific index without actually flickering the window through all the
   intermediate shapes.
 - Can I hook into the GNOME and KDE keybinding APIs without using PyKDE or
   gnome-python? (eg. using D-Bus, perhaps?)

@todo: Merge remaining appropriate portions of:
 - U{https://thomas.apestaart.org/thomas/trac/changeset/1123/patches/quicktile/quicktile.py}
 - U{https://thomas.apestaart.org/thomas/trac/changeset/1122/patches/quicktile/quicktile.py}
 - U{https://thomas.apestaart.org/thomas/trac/browser/patches/quicktile/README}

@todo 1.0.0: Retire L{__main__.KEYLOOKUP}. (API-breaking change)

@newfield appname: Application Name
"""  # NOQA

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__appname__ = "QuickTile"
__license__ = "GNU GPL 2.0 or later"

# vim: set sw=4 sts=4 expandtab :
