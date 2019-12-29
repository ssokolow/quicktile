=========
QuickTile
=========

.. image:: https://landscape.io/github/ssokolow/quicktile/master/landscape.png
   :target: https://landscape.io/github/ssokolow/quicktile/master
   :alt: Code Health

.. image:: https://scrutinizer-ci.com/g/ssokolow/quicktile/badges/quality-score.png?b=master
   :target: https://scrutinizer-ci.com/g/ssokolow/quicktile/?branch=master
   :alt: Scrutinizer Code Quality

.. image:: https://api.codacy.com/project/badge/Grade/5a3450aa0d2e429796a836580b1fef32
   :target: https://www.codacy.com/app/from_github/quicktile
   :alt: Codacy

.. image:: https://codeclimate.com/github/ssokolow/quicktile/badges/gpa.svg
   :target: https://codeclimate.com/github/ssokolow/quicktile
   :alt: Code Climate

.. image:: https://travis-ci.org/ssokolow/quicktile.svg?branch=master
   :target: https://travis-ci.org/ssokolow/quicktile
   :alt: Travis-CI

.. image:: https://coveralls.io/repos/github/ssokolow/quicktile/badge.svg?branch=master
   :target: https://coveralls.io/github/ssokolow/quicktile?branch=master
   :alt: Coveralls

Keyboard-driven Window Tiling for your existing X11 window manager

-------------------------------------------------
Important Message For Users of GTK+ 2.x QuickTile
-------------------------------------------------

As of QuickTile 0.4.0...

* The list of dependencies has changed significantly from PyGTK to PyGI
* The Xlib binding is now a required dependency due to regressions in the
  usability of certain GDK APIs.
* The ``middle`` command has been renamed to ``center`` for consistency with
  ``move-to-center``. While ``quicktile.cfg`` will be updated automatically,
  you will have to manually adjust any scripts which rely on calling
  ``quicktile middle`` as a subprocess or using it via the
  ``com.ssokolow.QuickTile.doCommand`` D-Bus API.
* If you are modifying QuickTile's internals, please contact me.
  I have begun a major refactoring and want to make sure that your
  modifications get updated accordingly.

-------------
Requirements:
-------------

* An X11-based desktop (The code expects NETWM hints and X11-style window
  decorations)
* Python 3.5+
* Python GI and its API definitions for the following libraries:

  * Gdk and GdkX11 3.x (``gir1.2-gtk-3.0``)
  * Wnck 3.x (``gir1.2-wnck-3.0``)
* setuptools
* python-xlib
* dbus-python (optional, required for D-Bus service)


Depending on the distro you are using, you may be able to use one of the
following commands to easily install them:

**Debian and derivatives (Ubuntu, Mint, etc.):**

.. code:: sh

    sudo apt-get install python3 python3-pip python3-setuptools python3-gi python3-xlib python3-dbus gir1.2-gtk-3.0 gir1.2-wnck-3.0

**TODO:** Determine the equivalent packages on Fedora

--------------------------
Installation (Typical Use)
--------------------------

After you have installed the above requirements via your system package
manager, you can install QuickTile using any of the following methods:

A. If you have ``pip3`` installed, just run this:

 .. code:: sh

     sudo pip3 install https://github.com/ssokolow/quicktile/archive/master.zip

 **NOTE:** If you attempt to use the ``--upgrade`` option and it fails to
 properly ignore system-provided dependencies, use the following commands to
 remove the old version, then reinstall.

 .. code:: sh

     sudo pip3 uninstall quicktile
     sudo rm /usr/local/bin/quicktile{,.py}

B. Without ``pip3``, download and unpack the zip file and run the following:

 .. code:: sh

     cd /path/to/local/copy
     ./install.sh

 Technically speaking, an ordinary ``sudo python3 setup.py install`` will also
 work, but ``install.sh`` has three advantages:

 1. It runs the ``setup.py build`` step without root privileges to avoid
    leaving root-owned cruft around.
 2. It will attempt to remove old QuickTile files which might cause a newer
    install to break.
 3. It saves you the trouble of setting QuickTile to run on startup.
    (``setup.py`` can't do this because it has no mechanism for adding files
    to ``/etc``.)

C. Without ``pip3``, if you don't want a system-wide install:

 1. Download and unpack the zip file.
 2. Copy the ``quicktile`` folder and the ``quicktile.sh`` script into a folder
    of your choice.
 3. Make sure ``quicktile.sh`` is marked executable.

 **NOTE:** If you'd rather roll your own, the ``quicktile.sh`` shell script is
 just three simple lines:

 1. The shebang
 2. A line to ``cd`` to wherever ``quicktile.sh`` is
 3. A line to run ``python3 -m quicktile "$@"``

**AFTER INSTALLING:**

1. Run ``quicktile`` once to generate your configuration file

   **NOTE:** If the ``quicktile`` command dies with a
   ``No module named __main__`` error, you probably have an old
   ``quicktile.py`` file in ``/usr/local/bin`` that needs to be deleted. If
   that doesn't fix the problem, you should still be able to run QuickTile as
   ``python3 -m quicktile`` instead.
2. Edit ``~/.config/quicktile.cfg`` to customize your keybinds

   **Note:** Customizing the available window shapes currently requires editing
   the source code (though it's quite simple). This will be remedied when I
   have time to develop a new config file format that supports hierarchical
   data.
3. Set your desktop to run ``quicktile --daemonize`` if you didn't use
   ``install.sh``.


Important Notes:
================

* If you are running a desktop which uses Compiz (such as Unity),
  make sure you've used CCSM to disable the grid plugin or the fight between
  it and QuickTile for the same type of functionality may cause unpredictable
  problems.
* You can list your current keybindings by running
  ``quicktile --show-bindings``
* You can get a list of valid actions for the configuration file by running
  ``quicktile --show-actions``

-------------------
Usage (Typical Use)
-------------------

1. Focus the window you want to tile
2. Hold the modifiers defined in ``ModMask`` (``Ctrl+Alt`` by default).
3. Repeatedly press one of the defined keybindings to cycle through window
   sizes available at the desired location on the screen.

The default keybindings are:

* ``1`` through ``9`` on the numeric keypad resize windows to the corresponding
  regions of whichever monitor it's currently on.
* ``Shift-1`` through ``Shift-9`` on the numeric keypad move windows to the
  corresponding regions without altering their dimensions.
* ``C`` is an alias for ``move-to-center`` which may be more memorable.
* ``0`` on the numeric keypad will fully maximize the active window.
* ``H`` and ``V`` will maximize a window horizontally or vertically.
* ``Enter`` on the numeric keypad will cycle the active window to the next
  monitor.

This works best when combined with functionality your existing window manager
provides (eg. ``Alt+Tab``) to minimize the need to switch your hand between your
keyboard and your mouse.

Keybinding Syntax
=================

Both the ``ModMask`` field and the ``[keys]`` section use GTK+ accelerator
syntax and you can use modifier keys in both places. (``ModMask`` is prepended
to each ``[keys]`` value before parsing it.)

GTK+ modifier syntax looks like this::

    <Ctrl><Alt>Delete

The important things to keep in mind for using it are:

1. **Do not** put any spaces inside your keybind string.
2. Modifier names and non-modifier key names are not the same thing.
3. Modifier names are case-insensitive.
4. Key names like ``Down`` are case-sensitive. (Don't let the letter keys fool
   you. Those work the way they do because ``A`` and ``a`` are two separate
   names for the same key.)

Valid Key Names
---------------

GTK+ key names are just X11 key symbols so the simplest way to identify the
name for a key is to use the ``xev`` command. Just run it in a terminal and
press the key you want. It will print out something like this:

| KeyPress event, serial 41, synthetic NO, window 0x8400001,
|    root 0x291, subw 0x0, time 2976251798, (149,-352), root:(192,460),
|    state 0x10, keycode 116 (keysym 0xff54, **Down**), same_screen YES,
|    XLookupString gives 0 bytes:
|    XmbLookupString gives 0 bytes:
|    XFilterEvent returns: False
|

The part I've bolded is the name QuickTile expects.

**Troubleshooting xev:**

* If nothing happens, make sure the ``xev`` window (and not the terminal) has
  focus.
* If pressing the key triggers some messages but you do not see one which says
  ``KeyPress event``, it's likely that some other program has already grabbed
  that key combination.

Also, in my testing, QuickTile currently fails to bind keys like ``Super_L``
(left Windows key) when they've been configured as modifiers. I'll look into
this as time permits.

Valid Modifier Names
--------------------

I haven't found a comprehensive document listing the modifier names
``gtk.accelerator_parse()`` accepts, but here are the names I'm aware of with
consistent mappings:

* Mappings that should be consistent across pretty much any system:

  * **Control:** ``<Control>``, ``<Ctrl>``, ``<Ctl>``, ``<Primary>``
  * **Shift:** ``<Shift>``, ``<Shft>``
  * **Alt:** ``<Alt>``, ``<Mod1>``
* Mappings which worked for me but I can't make any guarantees for:

  * **Windows Key:** ``<Mod4>``
  * **AltGr:** ``<Mod5>``
* Mappings which are possible but need to be manually set up using
  ``setxkbmap`` and ``xmodmap``:

  * ``<Mod3>`` (I redefined Caps Lock as ``Hyper_L`` and bound it to this)
* Modifiers which cause QuickTile to error out deep in ``python-xlib`` because
  GTK+ maps them to integers beyond the limits of the X11 wire protocol:

  * ``<Meta>``
  * ``<Super>``
  * ``<Hyper>``

-------------
Advanced Uses
-------------

* If you want to trigger QuickTile from another application in an efficient
  manner, make sure you have ``dbus-python`` installed and read up on how to
  send D-Bus messages using either your language's D-Bus bindings or the
  ``dbus-send`` or ``qdbus`` commands.
* If, for some reason, you want scripted tiling without D-Bus, you can also
  run commands like ``quicktile top-left`` but it may be slower as
  quicktile has to start, perform an action, and then quit every time you call
  it.

As with the built-in keybinding, requesting the same action more than once
in a row will cycle through the available window sizes. For further details,
see ``--help``.

----------
Known Bugs
----------

* ``pip3 uninstall`` doesn't remove the ``quicktile`` and/or ``quicktile.py``
  files from ``/usr/local/bin``, which can cause subsequent installs to
  break.

Thanks to Thomas Vander Stichele for some of the documentation cleanups.

-------
Removal
-------

As QuickTile does not yet have a one-command uninstall script, you will need to
do the following.

A. If you installed via ``pip3``...


.. code:: sh

    sudo pip3 uninstall quicktile
    sudo rm /usr/local/bin/quicktile


B. If you installed via ``install.sh``...

 ``install.sh`` doesn't yet log what it installed the way ``pip3`` does, so
 this will be a bit more involved.

 First, remove the system integration files:

 .. code:: sh

     # Remove the command that can be typed at the command-line
     sudo rm /usr/local/bin/quicktile

     # Remove the autostart file
     sudo rm /etc/xdg/autostart/quicktile.desktop

     # Remove the launcher menu entry
     sudo rm /usr/local/share/applications/quicktile.desktop

 Second, remove QuickTile itself from your Python packages folder.

 As development and release installations produce different file layouts,
 the way I recommend doing this is to run the following command, verify that
 nothing looks obviously wrong about the list of files and folders it
 produces, and then delete them:

 .. code:: sh

    find /usr/local/lib -iname 'quicktile*'
