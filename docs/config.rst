Configuration
=============

.. contents::
   :local:

QuickTile's behaviour is currently controlled by a ``.ini``-like configuration
file stored at :file:`~/.config/quicktile.cfg`.

It will be generated/regenerated from a set of defaults when QuickTile is run
if it does not exist.

At present, due to the ``.ini`` format's inability to handle arbitrary
hierarchical data, configuration beyond what is listed here requires modifying
QuickTile's source code, though it *is* planned to switch to a new
configuration format which will remedy this.

Configuration File Syntax
-------------------------

The configuration is split into two sections:

``[general]``
^^^^^^^^^^^^^

This section controls everything except keybindings, and currently recognizes
the following keys:

``cfg_schema = 1``
""""""""""""""""""

This key must be present and set to 1. It was included as a means for QuickTile
to identify the format of the config file if it becomes necessary to break
compatibility with the current setup without changing to an entirely new
file format.

.. _ColumnCount:

``ColumnCount = 3``
"""""""""""""""""""

This controls the number of steps that commands like :ref:`top-left <top-left>`
will cycle through and is used to derive the column width that steps other than
"half of the screen" will be multiples of.

Each preset will have :samp:`1 + {columns}` steps with the first step occupying
either half the monitor width or the full width, as appropriate.

It defaults to 3 for equivalence to WinSplit Revolution but you will probably
want to increase it if you have a particularly large or wide monitor.

At present, no provision is made to deduplicate this in the ``columns=2`` case
and, for larger multiples of 2, it is considered desirable to have "half
width" present both at the beginning of the sequence and at its natural
position in the progression.

There is currently no equivalent for modifying the number of rows because
each command hard-codes for a row or span of rows, and until QuickTile's
internals are renovated further, it is not possible to define new commands
without editing the code.

(However, the code in question is designed to be reasonably simple to edit
if you need to and can be found in
:func:`quicktile.layout.make_winsplit_positions`.)

.. _ModMask:

``ModMask = <Ctrl><Alt>``
"""""""""""""""""""""""""

This provides an easy way to set a shared prefix for all QuickTile keybindings.

For example, setting ``<Mod4>`` would turn a binding to ``KP_0`` into
:kbd:`Win` + :kbd:`Keypad 0`.

.. _MovementsWrap:

``MovementsWrap = True``
""""""""""""""""""""""""

This controls whether the :ref:`monitor-* <monitor-*>`,
:ref:`workspace-go-* <workspace-go-*>`, and
:ref:`workspace-send-* <workspace-send-*>` commands wrap around when they
reach the edge of the desktop/workspace.

(eg. Whether :ref:`workspace-go-left <workspace-go-left>` will take you to the
rightmost workspace if you call it enough times.)

.. _[keys]:

``[keys]``
^^^^^^^^^^

This section has no specific field names but, rather, allows you to map hotkey
sequences in to QuickTile commands.

A list of valid commands is available either in the :doc:`commands` section
or by running QuickTile with the
`-\\-show-actions <cli.html#cmdoption-quicktile-show-actions>`_ option in a
terminal.

Both the keys and values must parse as :any:`str`.

As an example of the correct format, here is the default contents of the
``[keys]`` section as of QuickTile 0.4:

.. code-block:: ini

    [keys]
    KP_0 = maximize
    KP_1 = bottom-left
    KP_2 = bottom
    KP_3 = bottom-right
    KP_4 = left
    KP_5 = center
    KP_6 = right
    KP_7 = top-left
    KP_8 = top
    KP_9 = top-right
    KP_Enter = monitor-switch
    <Shift>KP_1 = move-to-bottom-left
    <Shift>KP_2 = move-to-bottom
    <Shift>KP_3 = move-to-bottom-right
    <Shift>KP_4 = move-to-left
    <Shift>KP_5 = move-to-center
    <Shift>KP_6 = move-to-right
    <Shift>KP_7 = move-to-top-left
    <Shift>KP_8 = move-to-top
    <Shift>KP_9 = move-to-top-right
    V = vertical-maximize
    H = horizontal-maximize
    C = move-to-center

.. _keybinding-syntax:

Keybinding Syntax
-----------------

Both the ``ModMask`` field and the ``[keys]`` section use the syntax accepted
by :func:`Gtk.accelerator_parse` and you can use modifier keys in both places.
(``ModMask`` is prepended to each ``[keys]`` value before parsing it.)

GTK+ modifier syntax looks like this::

    <Ctrl><Alt>Delete

The important things to keep in mind for using it are:

1. **Do not** put any spaces inside your keybind string.
2. Modifier names and non-modifier key names are not the same thing.
3. Modifier names are case-insensitive.
4. Key names like ``Down`` are case-sensitive. (Don't let the letter keys fool
   you. Those work the way they do because ``A`` and ``a`` are two separate
   names for the same key.)

Valid Modifier Names
^^^^^^^^^^^^^^^^^^^^

I haven't found a comprehensive document listing the modifier names
:func:`Gtk.accelerator_parse` accepts, but here are the names I'm aware of with
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

Valid Key Names
^^^^^^^^^^^^^^^

GTK+ key names are just X11 key symbols so the simplest way to identify the
name for a key is to use the :manpage:`xev(1)` command. Just run it in a
terminal and press the key you want. It will print out something like this:

.. code-block:: none
  :emphasize-lines: 3

  KeyPress event, serial 41, synthetic NO, window 0x8400001,
     root 0x291, subw 0x0, time 2976251798, (149,-352), root:(192,460),
     state 0x10, keycode 116 (keysym 0xff54, Down), same_screen YES,
     XLookupString gives 0 bytes:
     XmbLookupString gives 0 bytes:
     XFilterEvent returns: False

The part you want is the ``Down`` inside the ``(keysym 0xff54, Down)``.

Troubleshooting :program:`xev`
""""""""""""""""""""""""""""""

* If nothing happens, make sure the :manpage:`xev(1)` window (and not the
  terminal) has focus.
* If pressing the key triggers some messages but you do not see one which says
  ``KeyPress event``, it's likely that some other program has already grabbed
  that key combination.

.. note:: QuickTile will fail to bind keys such as ``Super_L`` (left Windows
    key) as normal keys if they have been configured to function as modifiers.

    You can use the :manpage:`xmodmap(1)` command to view your current modifier
    assignments.

----

.. todo::

    * Move the descriptions of configuration file fields into the source
      code and then make the reference ReST programmatically generated.
    * Decide how the print stylesheet rules should handle code blocks too wide
      to fit on a portrait page.
