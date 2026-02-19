# QuickTile Wayland/GNOME Support

**Note:** Wayland support is currently limited to GNOME Shell, is in beta,
and is maintained on a best-effort basis.

This document describes how to use QuickTile on GNOME with Wayland.

## Overview

Wayland's security model prevents applications from capturing global hotkeys or
moving windows arbitrarily. QuickTile overcomes these limitations using:

1. **Window Calls extension** - A GNOME Shell extension that exposes window
   management via D-Bus
2. **GNOME custom keybindings** - System shortcuts that invoke QuickTile commands

## Requirements

- GNOME Shell (tested on GNOME 42+)
- [Window Calls](https://extensions.gnome.org/extension/4724/window-calls/) extension
  (required on **all** GNOME versions for window management via D-Bus)

## Installation

1. **Install system dependencies:**

   ```bash
   # Debian/Ubuntu
   sudo apt install python3 python3-pip python3-setuptools python3-gi \
       python3-xlib python3-dbus gir1.2-glib-2.0 gir1.2-gtk-3.0 \
       gir1.2-wnck-3.0 pipx git

   # Fedora
   sudo dnf install python3 python3-pip python3-setuptools python3-gobject \
       python3-xlib python3-dbus gtk3 libwnck3 pipx git

   # Arch
   sudo pacman -S python python-pip python-setuptools python-gobject \
       python-xlib python-dbus gtk3 libwnck3 python-pipx git
   ```

2. **Install Window Calls extension:**
   
   Visit https://extensions.gnome.org/extension/4724/window-calls/

3. **Clone and install QuickTile:**

   ```bash
   git clone https://github.com/ssokolow/quicktile.git ~/.local/src/quicktile
   pipx install ~/.local/src/quicktile --system-site-packages
   ```

4. **Generate default configuration:**

   ```bash
   quicktile
   ```

5. **Setup GNOME keybindings:**

   ```bash
   ~/.local/src/quicktile/setup-wayland-keybindings.sh
   ```

## Configuration

Edit `~/.config/quicktile.cfg` to customize:

```ini
[general]
cfg_schema = 1
ColumnCount = 6          # Number of width steps when cycling
UseWorkarea = True
ModMask = <Ctrl><Alt>    # Modifier keys for keybindings
MovementsWrap = True

[keys]
C = move-to-center
V = vertical-maximize
H = horizontal-maximize
K = left
L = center
; etc.
```

After editing, re-run the keybindings setup:

```bash
~/.local/src/quicktile/setup-wayland-keybindings.sh
```

> **Note:** Keybindings are managed by GNOME's custom shortcuts system, not by
> QuickTile's daemon. After any change to `quicktile.cfg` (keys or modifier),
> you must re-run `setup-wayland-keybindings.sh` for changes to take effect.
> Simply restarting QuickTile is not sufficient.

## Default Keybindings

All keybindings use `Ctrl+Alt` as modifier:

| Key | Action | Description |
|-----|--------|-------------|
| K | left | Left side, cycles through widths |
| L | center | Center column |
| Ñ / ; | right | Right side, cycles through widths |
| I | top-left | Top-left corner |
| O | top | Top half |
| P | top-right | Top-right corner |
| , | bottom-left | Bottom-left corner |
| . | bottom | Bottom half |
| / | bottom-right | Bottom-right corner |
| V | vertical-maximize | Full height, keep width (toggle) |
| H | horizontal-maximize | Full width, keep height (toggle) |
| C | move-to-center | Center window on screen |
| F | fullscreen | Toggle fullscreen |
| Up | maximize | Maximize window |
| Down | minimize | Minimize window |
| B | bordered | Toggle window decorations |

## How It Works

### Window Management

The `WaylandWindowManager` class communicates with GNOME Shell via D-Bus
through the Window Calls extension. It can:

- List all windows and their properties
- Move and resize windows
- Maximize, minimize, and close windows

### Keybinding Integration

Wayland's security model prevents applications from capturing global hotkeys
directly. QuickTile supports two approaches depending on your GNOME version:

QuickTile uses GNOME's custom keybindings via `gsettings`. The
`setup-wayland-keybindings.sh` script registers shortcuts in
`org.gnome.settings-daemon.plugins.media-keys` that invoke
`quicktile <command>`.

### State Persistence

Window state (for features like cycle position and maximize toggle) is stored
in `$XDG_RUNTIME_DIR/quicktile/wayland-state.json`. If `XDG_RUNTIME_DIR` is
not set, QuickTile falls back to `/tmp/quicktile-<uid>/wayland-state.json`.

## Troubleshooting

### Keybindings not working

1. Verify Window Calls extension is enabled:
   ```bash
   gnome-extensions list --enabled | grep window-calls
   ```

2. Re-run keybindings setup:
   ```bash
   ~/.local/src/quicktile/setup-wayland-keybindings.sh
   ```

3. Check for conflicts in Settings > Keyboard > Keyboard Shortcuts

### Window not moving

1. Test QuickTile manually:
   ```bash
   ~/.local/src/quicktile/quicktile.sh left
   ```

2. Check if Window Calls is responding:
   ```bash
   gdbus call --session --dest org.gnome.Shell \
       --object-path /org/gnome/Shell/Extensions/Windows \
       --method org.gnome.Shell.Extensions.Windows.List
   ```

### Conflicts with Tiling Assistant

The setup script automatically clears Tiling Assistant keybindings. If you
still have conflicts, manually clear them:

```bash
gsettings set org.gnome.shell.extensions.tiling-assistant tile-left-half "[]"
gsettings set org.gnome.shell.extensions.tiling-assistant tile-right-half "[]"
# ... etc
```

## Limitations

- **No native hotkey daemon:** QuickTile relies on GNOME custom keybindings
  (via `setup-wayland-keybindings.sh`) to trigger commands per-invocation.
- **GNOME only:** This implementation is specific to GNOME Shell.
- **Some features unavailable:** Window shading, always-on-top, and pinning
  are not supported under Wayland.

## Files

- `quicktile/wayland_wm.py` - Wayland window manager implementation
- `quicktile/wayland_keybinder.py` - Wayland keybinder (GNOME Shell GrabAccelerator D-Bus API)
- `setup-wayland-keybindings.sh` - GNOME keybindings configuration script
