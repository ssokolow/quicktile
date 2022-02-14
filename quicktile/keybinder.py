"""Xlib-based global hotkey-binding code"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

# Silence PyLint being flat-out wrong about MyPy type annotations and
# complaining about my grouped imports
# pylint: disable=unsubscriptable-object,wrong-import-order

import logging
from functools import reduce  # pylint: disable=redefined-builtin

import gi
gi.require_version('Gtk', '3.0')

from gi.repository import GLib, Gtk, Gdk
from Xlib import X
from Xlib.display import Display
from Xlib.error import BadAccess, DisplayConnectionError

from .util import powerset, XInitError

# -- Type-Annotation Imports --
from typing import (Any, Callable, Dict, Iterable, Iterator, Optional, Tuple,
                    Union)

# Used only in type comments
from typing import List  # NOQA pylint: disable=unused-import

from Xlib.error import XError
from Xlib.protocol.event import KeyPress as XKeyPress
from .commands import CommandRegistry
from .wm import WindowManager
# --


class KeyBinder(object):
    """A convenience class for wrapping `XGrabKey`_.

    :param x_display: An Xlib display handle. If :any:`None`, a new connection
        will be opened.

    :raises XInitError: Failed to open a new X connection.

    .. _XGrabKey: https://tronche.com/gui/x/xlib/input/XGrabKey.html
    """

    #: Modifiers whose state should not affect whether a binding fires
    #:
    #: .. todo:: Figure out how to set the modifier mask in X11 and use
    #:    :func:`Gtk.accelerator_get_default_mod_mask` to feed said code.
    ignored_modifiers = ['Mod2Mask', 'LockMask']

    #: Used in concert with :meth:`Xlib.display.Display.sync` to pass state
    #: from :meth:`cb_xerror` to :meth:`bind` so XGrabKey_ failure can be
    #: reported.
    keybind_failed = False

    def __init__(self, x_display: Display = None):
        try:
            self.xdisp = x_display or Display()
        except (UnicodeDecodeError, DisplayConnectionError) as err:
            raise XInitError("python-xlib failed with %s when asked to open"
                             " a connection to the X server. Cannot bind keys."
                             "\n\tIt's unclear why this happens, but it is"
                             " usually fixed by deleting your ~/.Xauthority"
                             " file and rebooting."
                             % err.__class__.__name__)

        self.xroot = self.xdisp.screen().root
        self._keys = {}  # type: Dict[Tuple[int, int], Callable]

        # Resolve these at runtime to avoid NameErrors
        self._ignored_modifiers = [getattr(X, name) for name in
                                   self.ignored_modifiers]  # type: List[int]

        # We want to receive KeyPress events
        self.xroot.change_attributes(event_mask=X.KeyPressMask)

        # Set up a handler to catch XGrabKey() failures
        self.xdisp.set_error_handler(self.cb_xerror)

        # Merge python-xlib into the GLib event loop
        # Source: http://www.pygtk.org/pygtk2tutorial/sec-MonitoringIO.html
        GLib.io_add_watch(self.xroot.display, GLib.PRIORITY_DEFAULT,
                         GLib.IO_IN, self.cb_xevent)

    def bind(self, accel: str, callback: Callable[[], None]) -> bool:
        """Bind a global key combination to a callback.

        :param accel: An accelerator as either a string to be parsed by
            :func:`Gtk.accelerator_parse` or a tuple as returned by it.)
        :param callback: The function to call when the key is pressed.

        :returns: A boolean indicating whether the provided keybinding was
            parsed successfully and didn't provoke an error from XGrabKey_.

        .. _XGrabKey: https://tronche.com/gui/x/xlib/input/XGrabKey.html
        """
        parsed = self.parse_accel(accel)
        if parsed:
            keycode, modmask = parsed
        else:
            return False

        # Ignore modifiers like Mod2 (NumLock) and Lock (CapsLock)
        self._keys[(keycode, 0)] = callback  # Null modifiers seem to be a risk
        for mmask in self._vary_modmask(modmask, self._ignored_modifiers):
            self._keys[(keycode, mmask)] = callback
            self.xroot.grab_key(keycode, mmask,
                                1, X.GrabModeAsync, X.GrabModeAsync)

        # If we don't do this, then nothing works.
        # I assume it flushes the XGrabKey calls to the server.
        self.xdisp.sync()

        # React to any cb_xerror that might have resulted from xdisp.sync()
        if self.keybind_failed:
            self.keybind_failed = False
            logging.warning("Failed to bind key. It may already be in use: %s",
                            accel)
            return False

        return True

    def cb_xerror(self, err: XError, request: Any):
        """Callback used to identify when attempts to bind keys fail.

        :param err: The error that was asynchronously returned.
        :param request: Unused. Just to match the required function signature.

        .. todo:: Make another attempt to get :class:`Xlib.error.CatchError`
            working or to retrieve more diagnostic information another way.
        """
        if isinstance(err, BadAccess):
            self.keybind_failed = True
        else:
            self.xdisp.display.default_error_handler(err)

    def cb_xevent(self, src: GLib.IOChannel, cond: GLib.IOCondition,
            handle: Optional[Display] = None) -> bool:
        """:func:`GLib.io_add_watch` callback to dispatch X events to more
        specific handlers.

        :param src: Not used. Just needed to satisfy ``GIOFunc`` signature.
        :param cond: Not used. Just to needed to satisfy ``GIOFunc`` signature.
        :param handle: A handle to the Xlib display object with pending events.
            A cached reference will be used if it is :any:`None`.
        :rtype: :any:`True`
        :returns: Always returns :any:`True` to prevent GLib from unsetting
            the watch.

        .. todo:: Make sure uncaught exceptions in :meth:`cb_xevent` are
            prevented from making QuickTile unresponsive in the general case.
        .. todo:: Switch to using :data:`python:typing.Literal` in the return
            signature once it's no longer necessary to support Python
            versions prior to 3.8.
        .. todo:: Move :meth:`cb_xevent` out of keybinder into the core since
            Xlib is no longer optional and dispatch should be shared with
            :mod:`quicktile.wm` for responding to panel reservation changes.
        """
        handle = handle or self.xroot.display

        for _ in range(0, handle.pending_events()):
            xevent = handle.next_event()
            if xevent.type == X.KeyPress:
                self.handle_keypress(xevent)

        # Necessary for proper function
        return True

    def handle_keypress(self, xevent: XKeyPress):
        """Resolve :class:`Xlib.protocol.event.KeyPress` events to the
        :class:`quicktile.commands.CommandRegistry` commands associated with
        them and then call the commands.


        .. todo:: Use a proper ``index`` argument for
            :meth:`Xlib.display.Display.keycode_to_keysym` in
            :meth:`handle_keypress`'s debug messaging.
        .. todo:: Only call the code to look up a human-readable name for a
            key event if the log level is high enough that it won't be wasted.
        """
        keysig = (xevent.detail, xevent.state)
        if keysig not in self._keys:
            logging.error("Received an event for an unrecognized keybind: "
                          "%s, %s", xevent.detail, xevent.state)
            return

        # Display a meaningful debug message
        ksym = self.xdisp.keycode_to_keysym(keysig[0], 0)
        gmod = Gdk.ModifierType(keysig[1])
        kbstr = Gtk.accelerator_name(ksym, gmod)
        logging.debug("Received keybind: %s", kbstr)

        # Call the associated callback
        self._keys[keysig]()

    def parse_accel(self, accel: str) -> Optional[Tuple[int, int]]:
        """Convert an :ref:`accelerator string <keybinding-syntax>` into the
        form XGrabKey_ needs.

        :param accel: The accelerator string.
        :returns: ``(keycode, modifier_mask)`` or :any:`None` on failure.
        """

        result = self._accel_to_keysym(accel)

        if result is None:
            return None
        keysym, modmask = result

        # Convert to what XGrabKey expects
        keycode = self.xdisp.keysym_to_keycode(keysym)
        if isinstance(modmask, Gdk.ModifierType):
            modmask = modmask.real

        return keycode, modmask

    @staticmethod
    def _accel_to_keysym(accel: str) -> Optional[Tuple[str, int]]:
        """Internal helper for :meth:`parse_accel` for all operations that
        don't need an open connection to the X server.

        Parses and validates an :ref:`accelerator string <keybinding-syntax>`
        but does not convert from a keysym to a keycode.

        (Separated out for testing purposes)

        .. doctest::

            >>> KeyBinder._accel_to_keysym("<Foo>C")
            >>> KeyBinder._accel_to_keysym("<Control>Foo")
            >>> KeyBinder._accel_to_keysym("<Super>C")
            >>> KeyBinder._accel_to_keysym("<Control>C")
            (99, <flags GDK_CONTROL_MASK of type Gdk.ModifierType>)
        """
        keysym, modmask = Gtk.accelerator_parse(accel)
        if not Gtk.accelerator_valid(keysym, modmask):
            logging.error("Invalid keybinding: %s", accel)
            return None

        #TODO: See if I can use things like Gdk.keyval_* to make it Just Work
        if modmask > 2**16 - 1:
            logging.error("Modifier out of range for XGrabKey "
                          "(int(modmask) > 65535). "
                          "Did you use <Super> instead of <Mod4>?")
            return None

        return keysym, modmask

    @staticmethod
    def _vary_modmask(
            modmask: Union[int, Gdk.ModifierType],
            ignored: Iterable[Union[int, Gdk.ModifierType]]
    ) -> Iterator[int]:
        """Generate all possible variations on ``modmask`` that need to be
        taken into consideration if we can't properly ignore the modifiers in
        ``ignored``. (Typically NumLock and CapsLock)

        :param modmask: An integer or :any:`Gdk.ModifierType` bitfield to be
            combinatorically grown.
        :param ignored: Integer or :any:`Gdk.ModifierType` modifiers to be
            combined with ``modmask``.

        :returns: The :any:`power set <quicktile.util.powerset>` of ``ignored``
            with ``modmask`` bitwise ORed onto each entry.

        .. doctest::

            >>> list(KeyBinder._vary_modmask(Gdk.ModifierType.MOD1_MASK, []))
            [8]
            >>> list(KeyBinder._vary_modmask(Gdk.ModifierType.MOD1_MASK,
            ...                              [Gdk.ModifierType.MOD2_MASK,
            ...                               Gdk.ModifierType.LOCK_MASK]))
            [8, 24, 10, 26]


        .. todo:: Decide whether to make this :meth:`_vary_modmask` public when
            I turn off documenting private members.
        """

        for ignored in powerset(ignored):
            imask = reduce(lambda x, y: int(x | y), ignored, 0)
            yield modmask | imask


def init(modmask: Optional[str],
         mappings: Dict[str, str],
         commands: CommandRegistry,
         winman: WindowManager,
         ) -> Optional[KeyBinder]:
    """Initialize the keybinder and bind the requested mappings

    :param modmask: A valid set of modifiers as accepted by
        :func:`Gtk.accelerator_parse`, ``none``, an empty string, or
        :any:`None`.
    :param mappings: A dict mapping :ref:`accelerator strings
        <keybinding-syntax>` to command names.
    :param commands: The command registry used to map command names to
        functions.
    :param winman: The interface commands should use to take action.
    :returns: An instance of :class:`KeyBinder` or :any:`None` if ``winman``
        didn't already have an X connection and attempting to open a new one
        met with failure.
    """
    # Allow modmask to be empty for keybinds which don't share a common prefix
    if not modmask or modmask.lower() == 'none':
        modmask = ''

    try:
        keybinder = KeyBinder(x_display=winman.x_display)
    except XInitError as err:
        logging.error("%s", err)
        return None
    else:
        # TODO: Take a mapping dict with pre-modmasked keys
        #       and pre-closured commands
        for key, func in mappings.items():
            def call(func=func):
                """Closure to resolve `func` and call it on a
                   `WindowManager` instance"""
                commands.call(func, winman)

            keybinder.bind(modmask + key, call)
    return keybinder
