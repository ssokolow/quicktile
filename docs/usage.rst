Usage
=====

QuickTile is built around a simple model of applying :doc:`tiling commands
<commands>` to either the active window or, for some commands, the
desktop as a whole.

These commands can be invoked in one of three ways:

.. contents::
   :local:

Global Hotkeys
--------------

If QuickTile is started with the
`-\-daemonize <cli.html#cmdoption-quicktile-d>`_ option, it will
try to bind global hotkeys as defined by the mappings in
:doc:`quicktile.cfg <config>`.

A typical use of QuickTile's hotkeys is:

1. Focus the window you want to tile (eg. with :kbd:`Alt` + :kbd:`Tab`)
2. Hold the modifiers defined in :ref:`ModMask <ModMask>` (:kbd:`Ctrl`
   :kbd:`Alt` by default).
3. Repeatedly press one of the keybindings to cycle through window
   sizes available at the requested location.

See the :doc:`commands` section for a listing of default keybindings and what
they do, or run ``quicktile --show-actions`` to list all available commands and ``quicktile --show-bindings`` to list commands that have hotkeys bound to them.

Command-Line Invocation
-----------------------

If QuickTile is started without ``--daemonize`` but with one or more positional
arguments, it will perform the given sequence of actions on the active
window (or, depending on the command, on the desktop as a whole) and then exit.

.. code-block:: shell-session

    $ quicktile top-left top-left

This is intended for incorporating QuickTile into shell scripts
or triggering it from places its internal keybinding system can't watch, such as
LIRC_-based remote controls via :manpage:`irexec(1)`.

If running this in a context where it is undesirable for your script to block
and display an error dialog upon encountering an unexpected bug in QuickTile,
please pass `-\-no-excepthook <cli.html#cmdoption-quicktile-no-excepthook>`_
when invoking QuickTile.

For more details on QuickTile's command-line interface, run ``quicktile
--help`` or see the :doc:`cli` section of this manual.

.. note:: Historically, QuickTile has received most of its testing under
    `-\-daemonize <cli.html#cmdoption-quicktile-d>`_ and command-line
    invocation has known bugs in how it interacts with the X server.

    Most notably, when multiple commands are specified on a single
    command-line, it triggers a race condition where QuickTile doesn't properly
    wait for a command's effects to take hold before the next command begins
    querying window shapes.

    The simplest demonstration of this on a mulit-monitor system is
    ``quicktile monitor-next top-left`` which will cause the ``top-left`` to
    reverse the effect of the ``monitor-next``.

    A fix for this is intended, but the non-trivial re-architecting involved
    means that I don't want to do it until after the automated test suite is
    sufficiently complete.

.. todo:: Fix the race conditions which prevent non-resident operation from
    functioning as expected.

.. _LIRC: http://lirc.org/
.. _XGrabKey: https://tronche.com/gui/x/xlib/input/XGrabKey.html

D-Bus API
---------

Command-line invocation is useful but it *does* have a tendency to induce
a perceptible delay between pressing a key/button and having the window
respond.

If `dbus-python <https://pypi.org/project/dbus-python/>`_ is installed, the
`-\-daemonize <cli.html#cmdoption-quicktile-d>`_ command-line option will also
attempt to claim the ``com.ssokolow.QuickTile`` service name.

It will expose a single object path (``/com/ssokolow/QuickTile``) with a single
interface (``com.ssokolow.QuickTile``) containing a single method
(``doCommand``) which can be used to call tiling commands as if invoked
by the global keybinding code.

A good way to test this out is using Qt's :command:`qdbus` command, which
serves as both a command-line D-Bus explorer and a client for calling D-Bus
methods.

.. code-block:: shell-session

    $ qdbus com.ssokolow.QuickTile
    /
    /com
    /com/ssokolow
    /com/ssokolow/QuickTile
    $ qdbus com.ssokolow.QuickTile /com/ssokolow/QuickTile
    method QString org.freedesktop.DBus.Introspectable.Introspect()
    method bool com.ssokolow.QuickTile.doCommand(QString command)
    $ qdbus com.ssokolow.QuickTile /com/ssokolow/QuickTile \
        doCommand top-left
    true
    [terminal window is repositioned to the screen's top-left quarter]

The more ubiquitous ``dbus-send`` command can also be used to accomplish the
same thing, but it's much less convenient to work with and cannot double as
a D-Bus browser:

.. code-block:: shell-session

    $ dbus-send --type=method_call       \
        --dest=com.ssokolow.QuickTile    \
        /com/ssokolow/QuickTile          \
        com.ssokolow.QuickTile.doCommand \
        string:top-left

The :any:`bool` returned by ``doCommand`` indicates whether the given name
was found in the list of registered tiling commands.

Both of these commands can also be used as drop-in replacements for the
command-line interface as long as ``quicktile --daemonize`` has been started
beforehand.

While it takes more work to set up, the D-Bus interface has two advantages over
the command-line interface:

* :command:`qdbus` and :command:`dbus-send` start more quickly than QuickTile,
  so this is likely to have lower latency even if being invoked from a shell
  script rather than doing a direct D-Bus call from a resident process to
  QuickTile.
* Because the D-Bus and X11 client libraries share the same `-\-daemonize <cli.html#cmdoption-quicktile-d>`_ event loop,
  the D-Bus interface is free from known race conditions currently
  affecting the command-line interface.
