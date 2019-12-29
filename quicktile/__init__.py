#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# pylint: disable=line-too-long,too-many-lines
"""QuickTile, a WinSplit clone for X11 desktops

Thanks to Thomas Vander Stichele for some of the documentation cleanups.

:todo:
 - Complete the automated test suite.
 - Finish refactoring the code to be cleaner and more maintainable.
 - Reconsider use of C{--daemonize}. That tends to imply self-backgrounding.
 - Look into supporting xcffib (the Python equivalent to C{libxcb}) for global
   keybinding.
 - Implement the secondary major features of WinSplit Revolution (eg.
   process-shape associations, locking/welding window edges, etc.)
 - Consider rewriting L{commands.cycle_dimensions} to allow command-line use to
   jump to a specific index without actually flickering the window through all
   the intermediate shapes.

:todo: Retire `__main__.KEYLOOKUP`. (API-breaking change)

:newfield appname: Application Name
"""  # NOQA

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__appname__ = "QuickTile"
__license__ = "GNU GPL 2.0 or later"
__docformat__ = "restructuredtext en"

# vim: set sw=4 sts=4 expandtab :
