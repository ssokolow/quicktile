"""Xlib-based global hotkey-binding code"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

import logging

import gobject, gtk
from Xlib import X
from Xlib.display import Display
from Xlib.error import BadAccess, DisplayConnectionError

from .util import powerset, XInitError

class KeyBinder(object):
    """A convenience class for wrapping C{XGrabKey}."""

    #: @todo: Figure out how to set the modifier mask in X11 and use
    #:        C{gtk.accelerator_get_default_mod_mask()} to feed said code.
    ignored_modifiers = ['Mod2Mask', 'LockMask']

    #: Used to pass state from L{handle_xerror}
    keybind_failed = False

    def __init__(self, xdisplay=None):
        """Connect to X11 and the Glib event loop.

        @param xdisplay: A C{python-xlib} display handle.
        @type xdisplay: C{Xlib.display.Display}
        """
        try:
            self.xdisp = xdisplay or Display()
        except (UnicodeDecodeError, DisplayConnectionError), err:
            raise XInitError("python-xlib failed with %s when asked to open"
                             " a connection to the X server. Cannot bind keys."
                             "\n\tIt's unclear why this happens, but it is"
                             " usually fixed by deleting your ~/.Xauthority"
                             " file and rebooting."
                             % err.__class__.__name__)

        self.xroot = self.xdisp.screen().root
        self._keys = {}

        # Resolve these at runtime to avoid NameErrors
        self.ignored_modifiers = [getattr(X, name) for name in
                self.ignored_modifiers]

        # We want to receive KeyPress events
        self.xroot.change_attributes(event_mask=X.KeyPressMask)

        # Set up a handler to catch XGrabKey() failures
        self.xdisp.set_error_handler(self.handle_xerror)

        # Merge python-xlib into the Glib event loop
        # Source: http://www.pygtk.org/pygtk2tutorial/sec-MonitoringIO.html
        gobject.io_add_watch(self.xroot.display,
                             gobject.IO_IN, self.handle_xevent)

    def bind(self, accel, callback):
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
        if isinstance(accel, basestring):
            # pylint: disable=no-member
            keysym, modmask = gtk.accelerator_parse(accel)
        else:
            keysym, modmask = accel

        if not gtk.accelerator_valid(keysym, modmask):  # pylint: disable=E1101
            logging.error("Invalid keybinding: %s", accel)
            return False

        if modmask > 2**16 - 1:
            logging.error("Modifier out of range for XGrabKey "
                          "(int(modmask) > 65535). "
                          "Did you use <Super> instead of <Mod4>?")
            return False

        # Convert to what XGrabKey expects
        keycode = self.xdisp.keysym_to_keycode(keysym)
        if isinstance(modmask, gtk.gdk.ModifierType):
            modmask = modmask.real

        # Ignore modifiers like Mod2 (NumLock) and Lock (CapsLock)
        for mmask in self._vary_modmask(modmask, self.ignored_modifiers):
            self._keys.setdefault(keycode, []).append((mmask, callback))
            self.xroot.grab_key(keycode, mmask,
                    1, X.GrabModeAsync, X.GrabModeAsync)

        # If we don't do this, then nothing works.
        # I assume it flushes the XGrabKey calls to the server.
        self.xdisp.sync()

        if self.keybind_failed:
            self.keybind_failed = False
            logging.warning("Failed to bind key. It may already be in use: %s",
                accel)

    def handle_xerror(self, err, _):
        """Used to identify when attempts to bind keys fail.
        @note: If you can make python-xlib's C{CatchError} actually work or if
               you can retrieve more information to show, feel free.
        """
        if isinstance(err, BadAccess):
            self.keybind_failed = True
        else:
            self.xdisp.display.default_error_handler(err)

    def handle_xevent(self, src, cond, handle=None):  # pylint: disable=W0613
        """Dispatch C{XKeyPress} events to their callbacks.

        @rtype: C{True}

        @todo: Make sure uncaught exceptions are prevented from making
            quicktile unresponsive in the general case.
        """
        handle = handle or self.xroot.display

        for _ in range(0, handle.pending_events()):
            xevent = handle.next_event()
            if xevent.type == X.KeyPress:
                if xevent.detail in self._keys:
                    for mmask, callback in self._keys[xevent.detail]:
                        if mmask == xevent.state:
                            # FIXME: Only call accelerator_name if --debug
                            # FIXME: Proper "index" arg for keycode_to_keysym
                            keysym = self.xdisp.keycode_to_keysym(
                                xevent.detail, 0)

                            # pylint: disable=no-member
                            kb_str = gtk.accelerator_name(keysym, xevent.state)
                            logging.debug("Received keybind: %s", kb_str)
                            callback()
                            break
                        elif mmask == 0:
                            logging.debug("X11 returned null modifier!")
                            callback()
                            break
                    else:
                        logging.error("Received an event for a recognized key "
                                  "with unrecognized modifiers: %s, %s",
                                  xevent.detail, xevent.state)

                else:
                    logging.error("Received an event for an unrecognized "
                        "keybind: %s, %s", xevent.detail, xevent.state)

        # Necessary for proper function
        return True

    @staticmethod
    def _vary_modmask(modmask, ignored):
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

def init(modmask, mappings, commands, winman):
    """Initialize the keybinder and bind the requested mappings"""
    # Allow modmask to be empty for keybinds which don't share a common prefix
    if not modmask or modmask.lower() == 'none':
        modmask = ''

    try:
        keybinder = KeyBinder()
    except XInitError as err:
        logging.error(err)
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
