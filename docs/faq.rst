Frequently Asked Questions
==========================

.. contents::
   :local:

Troubleshooting
---------------

``ModMask = Control Shift Mod1`` doesn't work
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This usually happens when something else is still holding a grab on the key
combinations you want to use.

The most common culprit is the Grid plugin for the Compiz window manager. To
resolve the conflict, disable the Grid plugin (or just the offending
keybindings) in :abbr:`CCSM (CompizConfig Settings Manager)` and then log out
and back in to ensure that the changes get applied.

To help in diagnosing this problem, QuickTile will attempt to report failure to
grab hotkeys when you start it with :command:`quicktile --daemonize` in a
terminal.

.. code-block:: none

    WARNING: Failed to bind key. It may already be in use: <Ctrl><Alt>KP_5

(However, this isn't 100% reliable because it is possible for your compositor
to implement global hotkeys by intercepting events before they reach
``XGrabKey``)

QuickTile positions windows over/under my panels
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The GTK+ 3.x version of QuickTile hasn't yet regained the ability to notice
changes to the available region of the desktop after it's started. Make sure
QuickTile gets launched after your panels have appeared.

Follow `Issue 107 <https://github.com/ssokolow/quicktile/issues/107>`_ for
status updates.

Quicktile treats all panels as if they're full-width/height
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In the move from GTK+ 2.x to GTK 3.x, the ``gtk.gdk.Region`` class got replaced
with ``cairo.Region`` and I've run into so many bugs while attempting to use it
from Python that I had to settle for implementing my own solution, which
doesn't yet know how to do anything fancier than calculating a "largest usable
rectangle" separately for each monitor.

.. todo:: Open an issue for `#95 (comment) <https://github.com/ssokolow/quicktile/issues/95#issuecomment-570089109>`_ on the tracker.

QuickTile resizes windows but doesn't move them
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Some window managers can be set to ignore requests by applications to move your
windows. This used to be a problem before QuickTile started announcing itself
to the system as a window-management utility, but it shouldn't be any longer.

If you are still experiencing this, please
`report it <https://github.com/ssokolow/quicktile/issues>`_ so the cause can
be investigated. While you wait, you can work around it by disabling the
misbehaving application protection in your window manager.

Under GNOME 2's Metacity WM, this was accomplished using the following
command:

.. code-block:: sh

   gconftool-2 --set "/apps/metacity/general/disable_workarounds" false --type bool

Terminator animates to zero width/height when resized
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This is a `bug <https://bugs.launchpad.net/terminator/+bug/1361252/comments/1>`_
in Terminator that both QuickTile and Xfwm's more limited built-in tiling
support can trigger.

Right-click your Terminator window, select Preferences, and then uncheck
"Window geomtry hints" in the Global tab.

It is my hope that QuickTile will become immune to it when I find time to
implement full support for taking windows' requested size restrictions into
account when calculating destination shapes.

Tiled windows are misaligned on a Compiz-based desktop
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This is `apparently
<https://github.com/ssokolow/quicktile/issues/70#issuecomment-270127825>`_
a symptom of a conflict between QuickTile and the Compiz Grid plugin.

Make sure you've disabled the Grid plugin in
:abbr:`CCSM (CompizConfig Settings Manager)`. If the problem persists, log out
and back in to ensure that the changes have taken effect.

Other Questions
---------------

When will you support Wayland?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    Never. Wayland's security model makes it impossible to move and resize
    windows belonging to other applications unless you are the compositor
    itself.

    You'll have to poke the creators of your compositor to improve tiling
    support or switch to a different compositor.

    Depending on how your compositor works, running QuickTile under XWayland
    may or may not allow it to see other X11 applications running under
    XWayland.

Does QuickTile run on macOS?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    It's not a primary target, since I don't have a Mac to test with, but if
    `SpectrWM <https://github.com/conformal/spectrwm/wiki/OSX>`_ can run via
    X11.app, QuickTile isn't out of the question.

    The GTK+ 2.x version of libwnck failed to retrieve the active window and
    development of a workaround
    `[1] <https://github.com/ssokolow/quicktile/issues/28>`_
    `[2] <https://github.com/ssokolow/quicktile/tree/xquartz>`_ stalled when I
    fell out of contact with the person who wanted it and no longer had anyone
    to test changes.

    I don't know whether the GTK 3.x version of libwnck is any better, but, if
    not and you're willing to test rapid-fire changes to the code, macOS
    support isn't out of the question.

    A list of shareware alternatives with official OSX support is also
    available on `StackOverflow <http://stackoverflow.com/questions/273242/is-there-anything-like-winsplit-revolution-for-mac-os-x>`_

QuickTile doesn't meet my needs. What can I do?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    You could contribute code or `file a feature request
    <https://github.com/ssokolow/quicktile/issues>`_ and wait.

    If that's not good enough, Wikipedia's `Tiling window manager
    <https://secure.wikimedia.org/wikipedia/en/wiki/Tiling_window_manager>`_
    page does contain a section listing other tools that might meet your needs.
    (Ones for other plaforms like Windows too, for that matter)
