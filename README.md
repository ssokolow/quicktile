# QuickTile, a WinSplit clone for X11 desktops

## Requirements:

 * An X11-based desktop (The code expects NETWM hints and X11-style window decorations)
 * Python 2.x (Tested with 2.5 on 2011-09-10. Developed on 2.7)
 * PyGTK 2.2 (assuming `get_active_window()` isn't newer than that)
 * `python-xlib` (optional, required for key-binding)
 * `dbus-python` (optional, required for D-Bus service)

If you are running an APT-based Linux distribution with Debian-compatible
package names (like the Ubuntu family of distros), you can install these
dependencies via your package manager by running this command:

    sudo apt-get install python python-gtk2 python-xlib python-dbus

Due to changes in how GTK+ and X11 are accessed, support for Python 3 is
non-trivial and has been delayed by the author's courseload.

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

Thanks to Thomas Vander Stichele for some of the documentation cleanups.
