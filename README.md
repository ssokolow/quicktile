# QuickTile
[![Code Health](https://landscape.io/github/ssokolow/quicktile/master/landscape.png)](https://landscape.io/github/ssokolow/quicktile/master)

Keyboard-driven Window Tiling for your existing X11 window manager

## Requirements:

 * An X11-based desktop (The code expects NETWM hints and X11-style window decorations)
 * Python 2.x (Tested with 2.5 on 2011-09-10. Developed on 2.7)
 * PyGTK 2.2 (assuming `get_active_window()` isn't newer than that)
 * `python-wnck`
 * `python-xlib` (optional, required for key-binding)
 * `dbus-python` (optional, required for D-Bus service)

Due to changes in how GTK+ and X11 are accessed, support for Python 3 is
non-trivial and has been delayed by the author's courseload.

Depending on the distro you are using, you may be able to use one of the
following commands to easily install them:

**Debian and derivatives (Ubuntu, Mint, etc.):**

    sudo apt-get install python python-gtk2 python-xlib python-dbus python-wnck

**Fedora 22 and above:**

    sudo dnf install python pygtk2 pygobject2 dbus-python gnome-python2-libwnck

**Fedora 21 and below:**

    sudo yum install python pygtk2 pygobject2 dbus-python gnome-python2-libwnck

## Installation (Typical Use)

 1. Make sure the requirements above are satisfied (including `python-xlib`)
 2. Extract `quicktile.py` to wherever you want to keep it
 3. Set `quicktile.py` to be executable if it isn't already
 4. Run `quicktile.py` once to generate your configuration file
 5. Edit `~/.config/quicktile.cfg` to customize your keybinds
 6. Set your desktop to run `quicktile.py --daemonize`

**Note:** Customizing the available window shapes currently requires editing
the source code (though it's quite simple). This will be remedied when the
author has time to decide between extending the standard Python rcfile parser
and replacing `quicktile.cfg` with `quicktile.json`.

**Note:** If you want to install QuickTile system-wide and have it auto-start,
the standard `sudo ./setup.py install` command should do the trick. Please let
me know if you experience any troubles.

### Important Notes:

 * If you are running a desktop which uses Compiz (such as Ubuntu's Unity),
   make sure you've used CCSM to disable the grid plugin or the fight between
   it and QuickTile for the same type of functionality may cause unpredictable
   problems.

 * Some systems may not provide a Python 2.x binary under the name `python2`.
   If this is the case on yours, you must edit the first line in `quicktile.py`
   accordingly.
 * If you are running quicktile from a folder that isn't in your `PATH`,
   you will need to specify a path like `./quicktile.py` to run `quicktile.py`
   directly.
 * If you don't mark `quicktile.py` as executable, you must run
   `python2 quicktile.py` rather than `quicktile.py`.
 * You can list your current keybindings by running
   `quicktile.py --show-bindings`
 * You can get a list of valid actions for the configuration file by running
   `quicktile.py --show-actions`

## Usage (Typical Use)

 1. Focus the window you want to tile
 2. Hold the modifiers defined in `ModMask` (`Ctrl+Alt` by default).
 3. Repeatedly press one of the defined keybindings to cycle through window
    sizes available at the desired location on the screen.

The default keybindings are:

 * `1` through `9` on the numeric keypad represent regions of your screen
 * `0` on the numeric keypad will fully maximize the active window.
 * `H` and `V` will maximize a window horizontally or vertically.
 * `Enter` on the numeric keypad will cycle the active window to the next monitor.

This works best when combined with functionality your existing window manager
provides (eg. `Alt+Tab`) to minimize the need to switch your hand between your
keyboard and your mouse.

## Keybinding Syntax

Both the `ModMask` field and the `[keys]` section use GTK+ accelerator syntax
and you can use modifier keys in both places. (`ModMask` is prepended to each `[keys]` value before parsing it.)

GTK+ modifier syntax looks like this:

    <Ctrl><Alt>Delete

The important things to keep in mind for using it are:

1. **Do not** put any spaces inside your keybind string.
3. Modifier names and non-modifier key names are not the same thing.
4. Modifier names are case-insensitive.
5. Key names like `Down` are case-sensitive. (Don't like the letter keys fool you. Those work the way they do because `A` and `a` are two separate names for the same key.)

### Valid Key Names

GTK+ key names are just X11 key symbols so the simplest way to identify the name for a key is to use the `xev` command. Just run it in a terminal and press the key you want. It will print out something like this:

> KeyPress event, serial 41, synthetic NO, window 0x8400001,<br>
> &nbsp;&nbsp;&nbsp;root 0x291, subw 0x0, time 2976251798, (149,-352), root:(192,460),<br>
> &nbsp;&nbsp;&nbsp;state 0x10, keycode 116 (keysym 0xff54, **Down**), same_screen YES,<br>
> &nbsp;&nbsp;&nbsp;XLookupString gives 0 bytes:<br>
> &nbsp;&nbsp;&nbsp;XmbLookupString gives 0 bytes:<br>
> &nbsp;&nbsp;&nbsp;XFilterEvent returns: False<br>

The part I've bolded is the name QuickTile expects.

**Troubleshooting xev:**

* If nothing happens, make sure the `xev` window (and not the terminal) has focus.
* If pressing the key triggers some messages but you do not see one which says `KeyPress event`, it's likely that some other program has already grabbed that key combination.

Also, in my testing, QuickTile currently fails to bind keys like `Super_L` (left Windows key) when they've been configured as modifiers. I'll look into this as time permits.

### Valid Modifier Names

I haven't found a comprehensive document listing the modifier names `gtk.accelerator_parse()` accepts, but here are the names I'm aware of with consistent mappings:

* Mappings that should be consistent across pretty much any system:
  * **Control:** `<Control>`, `<Ctrl>`, `<Ctl>`, `<Primary>`
  * **Shift:** `<Shift>`, `<Shft>`
  * **Alt:** `<Alt>`, `<Mod1>`
* Mappings which worked for me but I can't make any guarantees for:
  * **Windows Key:** `<Mod4>`
  * **AltGr:** `<Mod5>`
* Mappings which are possible but need to be manually set up using `setxkbmap` and `xmodmap`:
  * `<Mod3>` (I redefined Caps Lock as `Hyper_L` and bound it to this)
* Modifiers which cause QuickTile to error out deep in `python-xlib` because GTK+ maps them to integers beyond the limits of the X11 wire protocol:
  * `<Meta>`
  * `<Super>`
  * `<Hyper>`


## Advanced Uses

 * If you want to trigger QuickTile from another application in an efficient
   manner, make sure you have `dbus-python` installed and read up on how to
   send D-Bus messages using either your language's D-Bus bindings or the
   `dbus-send` command.
 * If, for some reason, you want scripted tiling without D-Bus, you can also
   run commands like `quicktile.py top-left` but it may be slower as quicktile
   has to start, perform an action, and then quit every time you call it.

As with the built-in keybinding, requesting the same action more than once
in a row will cycle through the available window sizes. For further details,
see `--help`.

## Known Bugs

* libwnck tries to flood the logging output with
  `Unhandled action type _OB_WM_ACTION_UNDECORATE\n\n` messages, which is
  [a bug](https://icculus.org/pipermail/openbox/2009-January/006025.html),
  and PyGTK doesn't expose the function needed to filter them away. As a
  result, the best QuickTile can do is pipe its output through grep, leaving a
  flood of blank lines since grep is finicky about matching them.

Thanks to Thomas Vander Stichele for some of the documentation cleanups.
