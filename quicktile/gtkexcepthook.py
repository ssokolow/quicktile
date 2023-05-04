#!/usr/bin/env python3
# pylint: disable=line-too-long
"""Graphical exception handler for PyGTK applications

Usage
-----

::

    import gtkexcepthook
    gtkexcepthook.enable(optional_reporting_callback)

Notes
-----

| ©2003 Gustavo J A M Carneiro gjc at inescporto.pt
| ©2004-2005 Filip Van Raemdonck
| ©2009, 2011, 2017, 2019 Stephan Sokolow

::

    http://www.daa.com.au/pipermail/pygtk/2003-August/005775.html
    Message-ID: <1062087716.1196.5.camel@emperor.homelinux.net>
    "The license is whatever you want."

Contains changes merged back from `qtexcepthook.py`_, a Qt 5 port of
:file:`gtkexcepthook.py` by Stephan Sokolow ©2019.

Changes from Van Raemdonck version:
 - Ported to PyGI and GTK 3.x
 - Refactored code for maintainability and added MyPy type annotations
 - Switched from auto-enable to :any:`gtkexcepthook.enable` to silence PyFlakes
   false positives. (Borrowed naming convention from cgitb)
 - Split out traceback import to silence PyFlakes warning.
 - Started to resolve PyLint complaints

.. todo:: Finish polishing :mod:`quicktile.gtkexcepthook` up to meet my code
    formatting and clarity standards.
.. todo:: Confirm there isn't any other generally-applicable information that
       could be included in the :mod:`quicktile.gtkexcepthook` debugging dump.

.. _qtexcepthook.py: https://gist.github.com/ssokolow/f5219e4c8e4bddbba4d08101969445d1

API Documentation
-----------------
"""  # NOQA

__author__ = "Gustavo J A M Carneiro; Filip Van Daemdonck; Stephan Sokolow"
__authors__ = [
    "Gustavo J A M Carneiro",
    "Filip Van Daemdonck",
    "Stephan Sokolow"]
__license__ = "whatever you want"

# Silence PyLint being flat-out wrong about MyPy type annotations and
# complaining about my grouped imports
# pylint: disable=unsubscriptable-object
# pylint: disable=wrong-import-order

import enum, inspect, linecache, logging, pydoc, textwrap, tokenize, keyword
import sys
from io import StringIO
from gettext import gettext as _
from pprint import pformat

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')

from gi.repository import Gdk, Gtk

# -- Type-Annotation Imports --
from typing import Any, Callable, Dict, Generator, Type, Tuple
from types import FrameType, TracebackType
# --

log = logging.getLogger(__name__)

# == Analyzer Backend ==


class Scope(enum.Enum):
    """The scope of a variable looked up by :any:`lookup`"""
    Builtin = 1
    Global = 2
    Local = 3
    NONE = None

    def __str__(self):
        """Override str() to return either the variant name or '?' for NONE"""
        if self.value is Scope.NONE:
            return '?'
        else:
            return str(self.name)[0].upper()


def lookup(name: str,
           frame: FrameType,
           local_vars: Dict[str, Any]
           ) -> Tuple[Scope, Any]:
    """Find the value for a given name in the given frame

    :param name: Name of the variable to look up.
    :param frame: A frame object originally retrieved via
        :any:`inspect.getinnerframes`.
    :param local_vars: A cached locals dict originally retrieved via
        :any:`inspect.getargvalues`.
    :returns: A tuple of a :any:`Scope` and the requested value.
    """
    if name in local_vars:
        return Scope.Local, local_vars[name]
    elif name in frame.f_globals:
        return Scope.Global, frame.f_globals[name]
    elif '__builtins__' in frame.f_globals:
        builtins = frame.f_globals['__builtins__']
        if isinstance(builtins, dict):
            if name in builtins:
                return Scope.Builtin, builtins[name]
        elif hasattr(builtins, name):
            return Scope.Builtin, getattr(builtins, name)
    return Scope.NONE, None


def tokenize_frame(
        frame_rec: inspect.FrameInfo
) -> Generator[tokenize.TokenInfo, None, None]:
    """Generator which produces a lexical token stream from a frame record

    .. todo: Add MyPy type signature for :func:`tokenize_frame`

    """
    fname, lineno = frame_rec[1:3]
    lineno_mut = [lineno]

    def readline(*args):
        """Callback to work around tokenize.generate_tokens's API"""
        if args:
            log.debug("readline with args: %r", args)
        try:
            return linecache.getline(fname, lineno_mut[0])
        finally:
            lineno_mut[0] += 1

    for token_tup in tokenize.generate_tokens(readline):
        yield token_tup


def gather_vars(frame_rec: inspect.FrameInfo,
                local_vars: Dict[str, Any]) -> Dict[str, Any]:
    """Extract all the local variables from the given traceback frame using
    :func:`lookup`.

    :param frame_rec: A frame info object originally retrieved via
        :any:`inspect.getinnerframes`.
    :param local_vars: A cached locals dict originally retrieved via
        :any:`inspect.getargvalues`.
    :returns: A dict of the local variables.
    """
    frame = frame_rec[0]
    all_vars, prev, name, scope = {}, None, '', None
    for token_tuple in tokenize_frame(frame_rec):
        t_type, t_str = token_tuple[0:2]
        if (t_type == tokenize.NAME and  # noqa pylint: disable=no-member
                t_str not in keyword.kwlist):
            if not name:
                assert not name and not scope  # nosec
                scope, val = lookup(t_str, frame, local_vars)
                name = t_str
            elif name[-1] == '.':
                try:
                    val = getattr(prev, t_str)
                except AttributeError:
                    # XXX skip the rest of this identifier only
                    break
                name += t_str

            try:
                if val:
                    prev = val
            except:  # noqa pylint: disable=bare-except
                log.debug('  found %s name %s val %s in %s for token %s',
                          scope, name, val, prev, t_str)
        elif t_str == '.':
            if prev:
                name += '.'
        else:
            if name:
                all_vars[name] = (scope, prev)
            prev, name, scope = None, '', None
            if t_type == tokenize.NEWLINE:  # pylint: disable=no-member
                break
    return all_vars


def analyse(exctyp: Type[BaseException],
            value: BaseException,
            tracebk: TracebackType,
            context_lines: int = 3,
            max_width: int = 80
            ) -> StringIO:
    """Generate a traceback, including the contents of variables in each
    stack frame.

    :param exctyp: Used for class name.
    :param value: Used for exception message.
    :param tracebk: Used for everything else.
    :param context_lines: See the ``context`` argument to
        :any:`inspect.getinnerframes`
    :param max_width: Width to hard word-wrap to.
    :returns: The formatted traceback

    .. todo:: Rethink ``max_width`` for :any:`quicktile.gtkexcepthook.analyse`.
        Both it and no hard-wrapping make readability sub-optimal. I really
        want some form of indent-aware word-wrapping.
    """
    trace = StringIO()
    frame_records = inspect.getinnerframes(tracebk, context_lines)

    frame_wrapper = textwrap.TextWrapper(width=max_width,
        initial_indent='\n  ', subsequent_indent=' ' * 4)

    trace.write('Traceback (most recent call last):')
    for frame_rec in frame_records:
        frame, fname, lineno, funcname, context, _cindex = frame_rec

        args_tuple = inspect.getargvalues(frame)
        all_vars = gather_vars(frame_rec, args_tuple[3])

        trace_frame = 'File {!r}, line {:d}, {}{}'.format(
            fname, lineno, funcname, inspect.formatargvalues(*args_tuple,
            formatvalue=lambda v: '=' + pydoc.text.repr(v)))

        trace.write(frame_wrapper.fill(trace_frame) + '\n')
        trace.write(''.join(['    ' + x.replace('\t', '  ')
            for x in context or [] if x.strip()]))

        if all_vars:
            trace.write('    Variables (B=Builtin, G=Global, L=Local):\n')
            for key, (scope, val) in all_vars.items():
                wrapper = textwrap.TextWrapper(width=max_width,
                    initial_indent='     - {:>12} ({}): '.format(
                        key, str(scope)[0].upper()),
                    subsequent_indent=' ' * 7)
                trace.write(wrapper.fill(pformat(val)) + '\n')

    trace.write('%s: %s' % (exctyp.__name__, value))
    return trace

# == GTK+ Frontend ==


class ExceptionHandler(object):
    """GTK-based graphical exception handler

    :param reporting_cb: A callback to be exposed via a :guilabel:`Report...`
        button which will receive the formatted traceback as a string.
    """

    def __init__(self, reporting_cb: Callable[[str], None] = None) -> None:
        self.reporting_cb = reporting_cb

    def make_info_dialog(self) -> Gtk.MessageDialog:
        """Initialize and return the top-level dialog"""
        dialog = Gtk.MessageDialog(transient_for=None, flags=0,
                                   message_type=Gtk.MessageType.WARNING,
                                   buttons=Gtk.ButtonsType.NONE)

        dialog.set_title(_("Bug Detected"))
        dialog.set_markup(_("<big><b>A programming error has been detected "
            "during the execution of this program.</b></big>"))

        secondary = _("It probably isn't fatal, but should be reported to "
            "the developers nonetheless.")

        if self.reporting_cb:
            dialog.add_button(_("Report..."), 3)
        else:
            secondary += _("\n\nPlease remember to include the contents of "
                           "the Details dialog.")
        dialog.format_secondary_text(secondary)

        dialog.add_button(_("Details..."), 2)
        dialog.add_button(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE)
        dialog.add_button(Gtk.STOCK_QUIT, 1)

        return dialog

    @staticmethod
    def make_details_dialog(parent: Gtk.MessageDialog, text: str
                            ) -> Gtk.MessageDialog:
        """Initialize and return the details dialog

        :param parent: A reference to the dialog from :any:`make_info_dialog`.
        :param text: The contents of the formatted traceback.
        """

        details = Gtk.Dialog(title=_("Bug Details"), transient_for=parent,
                             modal=True, destroy_with_parent=True)
        details.add_button(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE)

        textview = Gtk.TextView()
        textview.show()
        textview.set_editable(False)
        textview.set_monospace(True)

        swin = Gtk.ScrolledWindow.new()
        swin.show()
        swin.add(textview)
        details.vbox.pack_start(swin, True, True, 2)  # pylint: disable=E1101
        textbuffer = textview.get_buffer()
        textbuffer.set_text(text)

        # Set the default size to just over 60% of the screen's dimensions
        screen = Gdk.Screen.get_default()
        monitor = screen.get_monitor_at_window(parent.get_window())
        area = screen.get_monitor_geometry(monitor)
        width, height = area.width // 1.6, area.height // 1.6
        details.set_default_size(int(width), int(height))

        return details

    def __call__(self,
            exctyp: Type[BaseException],
            value: BaseException,
            tback: TracebackType):
        """Custom :any:`sys.excepthook` callback which displays a GTK dialog"""

        cached_tb = None
        dialog = self.make_info_dialog()
        while True:
            resp = dialog.run()

            if resp == 3 and self.reporting_cb:
                if cached_tb is None:
                    cached_tb = analyse(exctyp, value, tback).getvalue()
                self.reporting_cb(cached_tb)
            elif resp == 2:
                if cached_tb is None:
                    cached_tb = analyse(exctyp, value, tback).getvalue()
                details = self.make_details_dialog(dialog, cached_tb)
                details.run()
                details.destroy()
            elif resp == 1 and Gtk.main_level() > 0:
                Gtk.main_quit()

            # Only the "Details" dialog loops back when closed
            if resp != 2:
                break

        dialog.destroy()


def enable(reporting_cb: Callable[[str], None] = None):
    """Call this to set gtkexcepthook as the default exception handler

    :param reporting_cb: If provided, this callback will be exposed in the
        dialog as a :guilabel:`Report...` button.

        The function will receive the same formatted traceback visible via
        the :guilabel:`Details...` button.
    """

    # MyPy disabled pending a release of the fix to #797
    sys.excepthook = ExceptionHandler(reporting_cb)  # type: ignore


if __name__ == '__main__':
    class TestFodder(object):  # pylint: disable=too-few-public-methods
        """Just something interesting to show in the augmented traceback"""
        y = 'Test'

        def __init__(self):
            self.z = self  # pylint: disable=invalid-name
    x = TestFodder()
    w = ' e'

    enable()
    raise Exception(x.z.y + w)

# vim: set sw=4 sts=4 :
