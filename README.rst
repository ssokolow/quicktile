QuickTile
=========

Keyboard-driven Window Tiling for your existing X11 window manager

Requirements:
-------------

**Debian and derivatives (Ubuntu, Mint, etc.):**

.. code:: sh

    sudo apt-get install python3 python3-pip python3-setuptools python3-gi python3-xlib python3-dbus gir1.2-glib-2.0 gir1.2-gtk-3.0 gir1.2-wnck-3.0

**Fedora and derivatives:**

.. code:: sh

    sudo dnf install python3 python3-pip python3-setuptools python3-gobject python3-xlib python3-dbus gtk3 libwnck3

For other distros or for more details, please consult the `Dependencies
<http://ssokolow.com/quicktile/installation.html#dependencies>`_ section of the
manual.

Installation
------------

QuickTile can be run from the source folder without installation via the
``./quicktile.sh`` script.

For system-wide installation, the recommended option is ``pip3``, which will
record a log to allow easy uninstallation.

``sudo -H pip3 install https://github.com/ssokolow/quicktile/archive/master.zip``

QuickTile's dependence on PyGObject prevents a fully PyPI-based installation
option.

Consult the `Installation <http://ssokolow.com/quicktile/installation.html>`_
section of the manual for full details and alternative installation options.

**First-Run Instructions for Global Hotkeys:**

1. Run ``quicktile`` or ``./quicktile.sh`` once to generate your configuration
   file at ``~/.config/quicktile.cfg``.
2. Edit the keybindings as desired.
3. Run ``quicktile --daemonize`` or ``./quicktile.sh --daemonize`` to bind to
   global hotkeys.
4. If everything seems to be working, add ``quicktile --daemonize`` or
   ``/full/path/to/quicktile.sh --daemonize`` to the list of commands your
   desktop will run on login.

Consult the `Configuration <http://ssokolow.com/quicktile/config.html>`_
section of the manual for further details.

Important Notes:
^^^^^^^^^^^^^^^^

* If run in a terminal, QuickTile's ``--daemonize`` option will attempt to
  report any problems with claiming global hotkeys for itself.
* You can get a list of valid actions for the configuration file by running
  ``quicktile --show-actions``.
* You can list your current keybindings by running
  ``quicktile --show-bindings``.
* If you experience problems, please consult the `FAQ
  <http://ssokolow.com/quicktile/faq.html>`_ section of the manual before
  reporting an issue.

Usage (Typical)
---------------

1. Focus the window you want to tile
2. Hold the modifiers defined in ``ModMask`` (``Ctrl+Alt`` by default).
3. Repeatedly press one of the defined keybindings to cycle through window
   sizes available at the desired location on the screen.

Consult ``quicktile --show-bindings`` or the `Command Reference
<http://ssokolow.com/quicktile/commands.html>`_ section of the manual for a list
of default keybindings.

(For example, under default settings, repeatedly pressing ``Ctrl+Alt+7`` will
place the active window in the top-left corner of the screen and cycle it
through different width presets.)

This works best when combined with functionality your existing window manager
provides (eg. ``Alt+Tab``) to minimize the need to switch your hand between your
keyboard and your mouse.

See the `Usage <http://ssokolow.com/quicktile/usage.html>`_ section of the
manual for alternative ways to interact with QuickTile.

Removal
-------

If you used the installation instructions listed above, a system-wide
installation of QuickTile can be removed with the following commands:

.. code:: sh

    sudo pip3 uninstall quicktile
    sudo rm /usr/local/bin/quicktile

See the `Removal <http://ssokolow.com/quicktile/installation.html#removal>`_
section of the manual for instructions on clearing out files left behind by
other installation methods.

Contributing
------------

I welcome contributions.

The recommended approach to make sure minimal effort is wasted is to open an
issue indicating your interest in working on something. That way, I can let you
know if there are any non-obvious design concerns that might hold up my
accepting your pull requests.

If you're looking for something to do, a ready supply
of simple TODOs is split across two different mechanisms:

1. Run ``grep -R TODO *.py quicktile/`` in the project root.
2. Set ``todo_include_todos = True`` in ``docs/conf.py`` and run
   ``cd docs; make html`` to generate a version of the manual with a TODO
   listing on the top-level API documentation page.

See the `Developer's Guide <http://ssokolow.com/quicktile/developing.html>`_
for more information.
