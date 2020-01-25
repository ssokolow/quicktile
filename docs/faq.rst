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
grab hotkeys when you start it with
`-\\-daemonize <cli.html#cmdoption-quicktile-d>`_ in a terminal.

.. code-block:: none

    WARNING: Failed to bind key. It may already be in use: <Ctrl><Alt>KP_5

(However, this isn't 100% reliable because it is possible for your compositor
to implement global hotkeys by intercepting events before they reach
`XGrabKey`_)

.. _XGrabKey: https://tronche.com/gui/x/xlib/input/XGrabKey.html

QuickTile positions windows over/under my panels
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The GTK+ 3.x version of QuickTile hasn't yet regained the ability to notice
changes to the available region of the desktop after it's started. Make sure
QuickTile gets launched after your panels have appeared.

Follow `Issue 107 <https://github.com/ssokolow/quicktile/issues/107>`_ for
status updates.

Quicktile treats all panels as if they're full-width/height
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In the move from GTK+ 2.x to GTK 3.x, the `gtk.gdk.Region`_ class got replaced
with :class:`cairo.Region` and I've run into so many bugs while attempting to
use it from Python that I had to settle for implementing my own solution, which
doesn't yet know how to do anything fancier than calculating a "largest usable
rectangle" separately for each monitor.

Follow `Issue 108 <https://github.com/ssokolow/quicktile/issues/108>`_ for
status updates.

.. _gtk.gdk.Region: https://developer.gnome.org/pygtk/stable/class-gdkregion.html

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

Tiled windows have huge margins on Elementary OS
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This happens because, from QuickTile's perspective, the pretty shadows are
part of the window decorations.

I don't know of a proper fix, but you can work around this by removing them. To
do so, open :file:`/usr/share/themes/elementary/gtk-3.0/gtk-widgets.css` and
make the following change:

.. code-block:: css
   :caption: Before
   :lineno-start: 4033

   decoration {
       border-radius: 4px 4px 0 0;
       box-shadow:
           0 0 0 1px @decoration_border_color,
           0 14px 28px rgba(0, 0, 0, 0.35),
           0 10px 10px rgba(0, 0, 0, 0.22);
       margin: 12px;
   }

.. code-block:: css
   :caption: After
   :lineno-start: 4033

   decoration {
           box-shadow: none;
           border: none;
           padding: 0;
           margin: 1;
   }

Firefox windows have huge margins
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

As with Elementary OS, this is a bug related to how windows draw shadows.

I haven't narrowed down the specific conditions which trigger it yet, but it
can be worked around by disabling Firefox's support for using
:abbr:`CSD (Client-Side Decorations)` to put the tabs in the titlebar.
To do so:

1. Choose :menuselection:`&Customize` from the context menu for any toolbar or
   tab widget which does not define a custom context menu.
2. Uncheck the :guilabel:`Title Bar` checkbox in the bottom-left corner.
3. Click the :guilabel:`Done` button.

(Be aware that, when I enabled CSD for test purposes, it reset all my Firefox
window positions to my center monitor. I'm not sure if this is because it is my
primary monitor or if it's because it was the monitor containing the active
window.)

You can then recover the ability to have the top-most row of pixels on your
screen pass mouse events to the tab bar by disabling window decorations and
relying on :kbd:`Alt` and the left and right mouse buttons to move and resize
your Firefox windows in situations where you want mouse-based window
manipulation.

Under KDE, this can be accomplished through the :guilabel:`Window Rules`
control panel, accessible through the titlebar context menu (:kbd:`Alt`
+ :kbd:`F3`) as :menuselection:`&More Actions --> Special &Window Settings...`.

For Openbox-based desktops, the equivalent can be achieved by making this
modification to your Openbox configuration file:

.. code-block:: xml
    :caption: ~/.config/openbox/whatever.xml

    <openbox_config>
      <!-- ... -->
      <applications>
        <!-- ... -->
        <application name="Firefox" title="*Mozilla Firefox*">
          <decor>no</decor>
        </application>
      </applications>
    </openbox_config>

As a more generic solution, the `Devil's Pie`_ or `Devil's Pie 2`_ utilities
can retrofit window rules onto any window manager. (Devil's Pie 2 replaces the
original Devil's Pie's syntax with an embedded Lua runtime.)

The following script will serve the purpose for Devil's Pie:

.. code-block:: lisp
    :caption: ~/.devilspie/firefox.ds

    if (is (application_name) "Firefox") and (contains (window_name) "Mozilla Firefox")
                (begin
                    (undecorate)
                )

.. _Devil's Pie: https://wiki.gnome.org/Projects/DevilsPie
.. _Devil's Pie 2: https://www.nongnu.org/devilspie2/

I get an error when I try to run QuickTile
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You probably either lack a dependency or have bits of a previous installation
lying around. Follow the :ref:`Removal` instructions, make sure you have all
required dependencies installed, and try installing again.

If this does not fix it, try running QuickTile via ``./quicktile.sh`` or
or ``python3 -m quicktile`` instead.

If that works, then your ``setuptools`` is breaking when asked to install
packages which declare ``console_scripts``.

If it does not work, then `open an issue
<https://github.com/ssokolow/quicktile/issues>`_ and I'll try to help you.

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

.. _quicktile-macos:

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

.. _quicktile-windows:

QuickTile doesn't meet my needs. What can I do?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    You could contribute code or `file a feature request
    <https://github.com/ssokolow/quicktile/issues>`_ and wait.

    If that's not good enough, Wikipedia's `Tiling window manager
    <https://secure.wikimedia.org/wikipedia/en/wiki/Tiling_window_manager>`_
    page does contain a section listing other tools that might meet your needs.
    (Ones for other platforms like Windows too, for that matter)

    Another useful place for Windows users to look is the `alternativeTo page
    <https://alternativeto.net/software/winsplit-revolution/?license=free>`_
    for WinSplit Revolution.
