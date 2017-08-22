"""Xlib-based global hotkey-binding code"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

import logging

import gobject, gtk
from Xlib import X
from Xlib.display import Display
from Xlib.error import BadAccess, DisplayConnectionError

from .util import powerset, XInitError

# Allow MyPy to work without depending on the `typing` package
# (And silence complaints from only using the imported types in comments)
MYPY = False
if MYPY:
    # pylint: disable=unused-import
    from typing import (Any, Callable, Dict, Iterable, Iterator, List,  # NOQA
                        Optional, Sequence, Sized, Tuple)

    from Xlib.error import XError                          # NOQA
    from Xlib.protocol.event import KeyPress as XKeyPress  # NOQA
    from .commands import CommandRegistry                  # NOQA
    from .wm import WindowManager                          # NOQA
    from .util import CommandCB                            # NOQA
del MYPY

class KeyBinder(object):
    """A convenience class for wrapping C{XGrabKey}."""

    #: @todo: Figure out how to set the modifier mask in X11 and use
    #:        C{gtk.accelerator_get_default_mod_mask()} to feed said code.
    ignored_modifiers = ['Mod2Mask', 'LockMask']

    #: Used to pass state from L{cb_xerror}
    keybind_failed = False

    def __init__(self, xdisplay=None):  # type: (Optional[Display]) -> None
        """Connect to X11 and the Glib event loop.

        @param xdisplay: A C{python-xlib} display handle.
        @type xdisplay: C{Xlib.display.Display}
        """
        try:
            self.xdisp = xdisplay or Display()
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

        # Merge python-xlib into the Glib event loop
        # Source: http://www.pygtk.org/pygtk2tutorial/sec-MonitoringIO.html
        gobject.io_add_watch(self.xroot.display,
                             gobject.IO_IN, self.cb_xevent)

    def bind(self, accel, callback):  # type: (str, Callable[[], None]) -> bool
        """Bind a global key combination to a callback.

        @param accel: An accelerator as either a string to be parsed by
            C{gtk.accelerator_parse()} or a tuple as returned by it.)
        @param callback: The function to call when the key is pressed.

        @type accel: C{str} or C{(int, gtk.gdk.ModifierType)} or C{(int, int)}
        @type callback: C{function}

        @returns: A boolean indicating whether the provided keybinding was
            parsed successfully. (But not whether it was registered
            successfully due to the asynchronous nature of the C{XGrabKey}
            request.)
        @rtype: C{bool}
        """
        keycode, modmask = self.parse_accel(accel)
        if keycode is None or modmask is None:
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

    def cb_xerror(self, err, _):  # type: (XError, Any) -> None
        """Used to identify when attempts to bind keys fail.
        @note: If you can make python-xlib's C{CatchError} actually work or if
               you can retrieve more information to show, feel free.
        """
        if isinstance(err, BadAccess):
            self.keybind_failed = True
        else:
            self.xdisp.display.default_error_handler(err)

    def cb_xevent(self, src, cond, handle=None):  # pylint: disable=W0613
        # type: (Any, Any, Optional[Display]) -> bool
        """Callback to dispatch X events to more specific handlers.

        @rtype: C{True}

        @todo: Make sure uncaught exceptions are prevented from making
            quicktile unresponsive in the general case.
        """
        handle = handle or self.xroot.display

        for _ in range(0, handle.pending_events()):
            xevent = handle.next_event()
            if xevent.type == X.KeyPress:
                self.handle_keypress(xevent)

        # Necessary for proper function
        return True

    def handle_keypress(self, xevent):  # type: (XKeyPress) -> None
        """Dispatch C{XKeyPress} events to their callbacks."""
        keysig = (xevent.detail, xevent.state)
        if keysig not in self._keys:
            logging.error("Received an event for an unrecognized keybind: "
                          "%s, %s", xevent.detail, xevent.state)
            return

        # Display a meaningful debug message
        # FIXME: Only call this code if --debug
        # FIXME: Proper "index" arg for keycode_to_keysym
        ksym = self.xdisp.keycode_to_keysym(keysig[0], 0)
        kbstr = gtk.accelerator_name(ksym, keysig[1])  # pylint: disable=E1101
        logging.debug("Received keybind: %s", kbstr)

        # Call the associated callback
        self._keys[keysig]()

    def parse_accel(self, accel  # type: str
                    ):  # type: (...) -> Tuple[Optional[int], Optional[int]]
        """Convert an accelerator string into the form XGrabKey needs."""

        keysym, modmask = gtk.accelerator_parse(accel)  # pylint: disable=E1101
        if not gtk.accelerator_valid(keysym, modmask):  # pylint: disable=E1101
            logging.error("Invalid keybinding: %s", accel)
            return None, None

        if modmask > 2**16 - 1:
            logging.error("Modifier out of range for XGrabKey "
                          "(int(modmask) > 65535). "
                          "Did you use <Super> instead of <Mod4>?")
            return None, None

        # Convert to what XGrabKey expects
        keycode = self.xdisp.keysym_to_keycode(keysym)
        if isinstance(modmask, gtk.gdk.ModifierType):
            modmask = modmask.real

        return keycode, modmask

    @staticmethod
    def _vary_modmask(modmask, ignored):
        # type: (int, Sequence[int]) -> Iterator[int]
        """Generate all possible variations on C{modmask} that need to be
        taken into consideration if we can't properly ignore the modifiers in
        C{ignored}. (Typically NumLock and CapsLock)

        @param modmask: A bitfield to be combinatorically grown.
        @param ignored: Modifiers to be combined with C{modmask}.

        @type modmask: C{int} or C{gtk.gdk.ModifierType}
        @type ignored: C{list(int)}

        @rtype: generator of C{type(modmask)}
        """

        for ignored in powerset(ignored):
            imask = reduce(lambda x, y: x | y, ignored, 0)
            yield modmask | imask

def init(modmask,   # type: Optional[str]
         mappings,  # type: Dict[str, CommandCB]
         commands,  # type: CommandRegistry
         winman     # type: WindowManager
         ):         # type: (...) -> Optional[KeyBinder]
    """Initialize the keybinder and bind the requested mappings"""
    # Allow modmask to be empty for keybinds which don't share a common prefix
    if not modmask or modmask.lower() == 'none':
        modmask = ''

    try:
        keybinder = KeyBinder()
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
