Installation
============

.. contents::
   :local:

There are three official installation methods for QuickTile, each with its own
advantages and disadvantages.

Support for other methods will be provided on a best-effort basis.

.. _Dependencies:

Dependencies
------------

Because QuickTile relies on library bindings which are not installable through
:abbr:`PyPI (the Python Package Index)`, :file:`setup.py` cannot be used to
automatically retrieve dependencies.

You must install the following separately (see below for APT and DNF commands):

A desktop based on the X11 windowing system
    QuickTile relies on NETWM hints and X11-style window decorations to do
    its work and Wayland's security model explicitly prevents tools like
    QuickTile from being written.

    If you are running MacOS, see the :ref:`quicktile-macos` FAQ entry.

    If you are running Windows and don't want to download WinSplit Revolution
    from an archive of discontinued software, there are some links which
    include Windows offerings in the :ref:`quicktile-windows` FAQ entry.
Python_ 3.5+
    QuickTile is developed in Python 3.x with Kubuntu Linux 16.04 LTS as its
    earliest explicitly tested compatibility target.
GTK_ 3.x
    QuickTile is built around a GLib event loop and also relies on GDK for
    certain window operations.
libwnck_
    QuickTile relies on libwnck for most of its window manipulation to avoid
    playing whac-a-mole with the quirks of various window managers.
PyGObject_
    QuickTile accesses GNOME-family libraries via their GObject Introspection
    APIs. If your distro packages the following GIR definition files separately
    from the corresponding libraries, you must also ensure that they are
    installed:

    * ``GLib-2.0`` (``gir1.2-glib-2.0`` on Debian-family distros)
    * ``Gdk-3.0`` and ``GdkX11-3.0``
      (``gir1.2-gtk-3.0`` on Debian-family distros)
    * ``Wnck-3.0`` (``gir1.2-wnck-3.0`` on Debian-family distros)
setuptools_
    Though a fairly standard dependency for modern :file:`setup.py` scripts,
    setuptools is not a part of the Python standard library proper and is often
    not part of the set of packages installed by default on Debian-family
    distros.
python-xlib_
    GDK 3.x and libwnck do not provide wrappers for required functionality,
    such as desktop-agnostic global keybinding and usable getting/setting of
    X11 window properties.
dbus-python_
    Optional, but required if you want to interact with QuickTile over D-Bus.

.. _dbus-python: https://pypi.org/project/dbus-python/
.. _GTK: https://www.gtk.org/download/index.php
.. _libwnck: https://gitlab.gnome.org/GNOME/libwnck
.. _PyGObject: https://pygobject.readthedocs.io/en/latest/
.. _Python: https://www.python.org/
.. _python-xlib: https://pypi.org/project/python-xlib/
.. _setuptools: https://pypi.org/project/setuptools/

Debian and derivatives (Ubuntu, Mint, etc.)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The following command should be sufficient to install all required
dependencies:

.. code:: sh

    sudo apt-get install python3 python3-pip python3-setuptools python3-gi python3-xlib python3-dbus gir1.2-glib-2.0 gir1.2-gtk-3.0 gir1.2-wnck-3.0

If you have `AptURL <https://help.ubuntu.com/community/AptURL>`_ set up,
you can also `click here <apt:python3,python3-pip,python3-setuptools,python3-gi,python3-xlib,python3-dbus,gir1.2-glib-2.0,gir1.2-gtk-3.0,gir1.2-wnck-3.0>`_
to trigger an installation prompt.

Fedora and derivatives
^^^^^^^^^^^^^^^^^^^^^^

The following command should be sufficient to install all required
dependencies:

.. code:: sh

    sudo dnf install python3 python3-pip python3-setuptools python3-gobject python3-xlib python3-dbus gtk3 libwnck3

Installation Options
--------------------

A. :command:`pip3` from a URL
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Advantages:**

* Simple
* Logs installed files for removal

**Disadvantages:**

* System-wide install (requires :command:`sudo`)
* Setting QuickTile to run on login must be done manually
* Does not allow you to modify QuickTile code before installation
* Requires :command:`pip3` to be installed

**Instructions:**

After installing your dependencies, run the following command to install
QuickTile:

.. code:: sh

    sudo pip3 install https://github.com/ssokolow/quicktile/archive/master.zip

.. note:: If you attempt to use the ``--upgrade`` option and it fails to
    properly ignore system-provided dependencies, follow the instructions
    in the `Removal`_ section and then try again.

B. :file:`install.sh` from a local folder
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Advantages:**

* No additional dependencies
* Adds QuickTile as a default autostart task for all desktop sessions
* Automatically attempts to remove old QuickTile installs before upgrading
* Allows local modifications before installation
* Still reasonably simple

**Disadvantages:**

* System-wide install (requires :command:`sudo`)
* Does not log installed files like :command:`pip3`
* Does not allow per-user modifications to the code after installation
* Must manually download and unpack QuickTile before running the installation
  command.

**Instructions:**

After installing your dependencies and downloading a copy of QuickTile
(`zip <http://github.com/ssokolow/quicktile/zipball/master>`_,
`tar <http://github.com/ssokolow/quicktile/tarball/master>`_, or
`git clone <https://github.com/ssokolow/quicktile.git>`_), run the
following commands to install it:

.. code:: sh

    cd /path/to/unpacked/quicktile
    ./install.sh

You will be prompted for your :command:`sudo` password.

.. note::
   While an ordinary ``sudo python3 setup.py install`` will also work,
   ``install.sh`` has three advantages:

   1. It runs the ``setup.py build`` step without root privileges to avoid
      leaving root-owned cruft around.
   2. It will attempt to remove old QuickTile files which might cause a newer
      install to break.
   3. It saves you the trouble of setting QuickTile to run on startup.
      (``setup.py`` can't do this because it has no mechanism for adding files
      to ``/etc``.)

.. todo:: Check whether ``./install.sh`` Just Works™ under
    `checkinstall <https://asic-linux.com.mx/~izto/checkinstall/>`_
    and, if so, suggest it as an option for making QuickTile easily
    uninstallable on platforms that no proper package is provided for.

.. _install_quicktile.sh:

C. Run QuickTile without installing it
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Advantages:**

* No additional dependencies
* :command:`sudo` not required
* Allows full customization of QuickTile
* Allows parallel installation of multiple QuickTile versions for development
  or testing purposes.
* Easy removal or upgrade (just delete/replace the folder)

**Disadvantages:**

* Multiple copies of QuickTile may be present on a multi-user system
* QuickTile must be set to run on startup manually
* Must manually make provisions for being able to call :file:`quicktile.sh`
  without placing it in your :envvar:`PATH`.

**Instructions:**

 1. `Download <http://github.com/ssokolow/quicktile/zipball/master>`_ or
    `clone <https://github.com/ssokolow/quicktile.git>`_ QuickTile.
 2. Copy the :file:`quicktile` folder and the :file:`quicktile.sh` script into
     a folder of your choice.
 3. Make sure :file:`quicktile.sh` is marked executable.

.. note:: If you'd rather roll your own, the :file:`quicktile.sh` shell script
    is just three simple lines:

    1. The shebang
    2. A line to ``cd`` to wherever the :file:`quicktile` folder is
    3. A line to run :code:`python3 -m quicktile "$@"`

Setting Up Global Hotkeys
-------------------------

1. Run :command:`quicktile` (or :command:`./quicktile.sh` if appropriate) in a
   terminal to create :file:`~/.config/quicktile.cfg`.

   .. note:: If the ``quicktile`` command dies with a
      ``No module named __main__`` error, you probably have an old copy of
      QuickTile that didn't get properly installed/removed.

      Try following the `Removal`_ instruction and repeating the installation
      process.

      If this doesn't fix the problem, you should still be able to run
      QuickTile as :code:`python3 -m quicktile` instead.

2. Edit :file:`~/.config/quicktile.cfg` to customize your keybindings. (See
   :doc:`config` for further details.)

   .. note:: Customizing the tiling presets beyond altering the number of
      of columns which window widths will cycle through currently requires
      editing the source code.

      (Though it *is* quite simple. Just edit the
      :func:`quicktile.layout.make_winsplit_positions` function.)

      This will be remedied when I have time to design a new config file
      format that supports hierarchical data and write and test the requisite
      code to migrate existing configuration files to the new format.

3. If you didn't use :file:`install.sh`, set your desktop to run
   ``quicktile --daemonize`` or ``/full/path/to/quicktile.sh --daemonize``
   on login.

4. Run ``quicktile --daemonize`` (or ``./quicktile.sh --daemonize`` if
   appropriate) in a terminal to see if it reports any keybinding failures
   and test whether the keybindings work as intended.

5. If QuickTile appears to be working correctly, use :kbd:`Ctrl` + :kbd:`C` to
   quit it, close the terminal, and re-launch it via your :guilabel:`Run...`
   dialog so you won't have a terminal hanging around unnecessarily.

6. Enjoy. :)

.. _Removal:

Removal
-------

As QuickTile does not yet have a one-command uninstall script, you will need to
do the following.

**A. If you installed via pip3...**


.. code:: sh

    sudo pip3 uninstall quicktile
    sudo rm /usr/local/bin/quicktile

.. todo:: Check whether :command:`pip3` is still failing to remove the
    ``console_scripts`` entry-points that it generates.


**B. If you installed via install.sh...**

 ``install.sh`` doesn't yet log what it installed the way ``pip3`` does, so
 this will be a bit more involved.

 1. Remove the system integration files:

    .. code:: sh

        # Remove the command that can be typed at the command-line
        sudo rm /usr/local/bin/quicktile

        # Remove the autostart file
        sudo rm /etc/xdg/autostart/quicktile.desktop

        # Remove the launcher menu entry
        sudo rm /usr/local/share/applications/quicktile.desktop

 2. Remove QuickTile from your Python packages folder.

    While QuickTile itself should be installed as a single folder with a name
    like :file:`QuickTile-0.4-py3.5.egg`, the paths have varied from distro to
    distro and Python version to Python version.

    To ensure a clean removal, I recommend running the following command,
    verifying that nothing looks obviously wrong about its output, and then
    deleting what it found:

    .. code:: sh

       find /usr/local/lib -iname 'quicktile*'

**C. If you run quicktile.sh without installing**

1. Delete your :file:`quicktile` folder and :file:`quicktile.sh` script.
2. Undo whatever changes you made to call :file:`quicktile.sh`. (eg.
   :envvar:`PATH` modifications, shell aliases, desktop session autorun
   entries, etc.)
