#!/bin/bash
# Setup QuickTile keybindings for GNOME Wayland using custom shortcuts

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
SCHEMA="org.gnome.settings-daemon.plugins.media-keys"
CUSTOM_SCHEMA="org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"
PATH_BASE="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings"

if ! command -v gsettings &> /dev/null; then
    echo "Error: gsettings not found. This script requires GNOME."
    exit 1
fi

QUICKTILE="$SCRIPT_DIR/quicktile.sh"
if [ ! -f "$QUICKTILE" ]; then
    echo "Error: quicktile.sh not found at $QUICKTILE"
    exit 1
fi

# Read keybindings from quicktile config
CONFIG="$HOME/.config/quicktile.cfg"

if [ ! -f "$CONFIG" ]; then
    echo "QuickTile config not found at $CONFIG"
    exit 1
fi

# Step 1: Clear Tiling Assistant keybindings to prevent conflicts
echo "Clearing Tiling Assistant keybindings..."
gsettings set org.gnome.shell.extensions.tiling-assistant center-window "[]"
gsettings set org.gnome.shell.extensions.tiling-assistant tile-left-half "[]"
gsettings set org.gnome.shell.extensions.tiling-assistant tile-right-half "[]"
gsettings set org.gnome.shell.extensions.tiling-assistant tile-top-half "[]"
gsettings set org.gnome.shell.extensions.tiling-assistant tile-bottom-half "[]"
gsettings set org.gnome.shell.extensions.tiling-assistant tile-topleft-quarter "[]"
gsettings set org.gnome.shell.extensions.tiling-assistant tile-topright-quarter "[]"
gsettings set org.gnome.shell.extensions.tiling-assistant tile-bottomleft-quarter "[]"
gsettings set org.gnome.shell.extensions.tiling-assistant tile-bottomright-quarter "[]"
gsettings set org.gnome.shell.extensions.tiling-assistant tile-maximize "[]"
gsettings set org.gnome.shell.extensions.tiling-assistant tile-maximize-horizontally "[]"
gsettings set org.gnome.shell.extensions.tiling-assistant tile-maximize-vertically "[]"
echo "Tiling Assistant keybindings cleared."
echo ""

# Parse the modifier mask from config
MODMASK=$(grep -E "^ModMask\s*=" "$CONFIG" | sed 's/ModMask\s*=\s*//' | tr -d ' ')
echo "Using modifier: $MODMASK"

# Read keybindings from the [keys] section of the config
declare -a BINDINGS=()
in_keys=false
while IFS= read -r line; do
    # Detect [keys] section
    if [[ "$line" =~ ^\[keys\] ]]; then
        in_keys=true
        continue
    fi
    # Exit when another section starts
    if [[ "$line" =~ ^\[.+\] ]]; then
        in_keys=false
        continue
    fi
    if $in_keys; then
        # Skip comments and empty lines
        [[ "$line" =~ ^[[:space:]]*[#\;] ]] && continue
        [[ -z "${line// }" ]] && continue
        # Parse "key = command"
        key=$(echo "$line" | sed 's/\s*=.*//' | tr -d ' ')
        cmd=$(echo "$line" | sed 's/^[^=]*=\s*//' | tr -d ' ')
        [ -n "$key" ] && [ -n "$cmd" ] && BINDINGS+=("$key:$cmd")
    fi
done < "$CONFIG"

if [ ${#BINDINGS[@]} -eq 0 ]; then
    echo "No keybindings found in [keys] section of $CONFIG"
    exit 1
fi

echo "Found ${#BINDINGS[@]} keybindings in config"

# Build paths array
PATHS=()
for i in "${!BINDINGS[@]}"; do
    PATHS+=("'$PATH_BASE/quicktile$i/'")
done

# Set the custom keybindings list
PATHS_STR=$(IFS=,; echo "${PATHS[*]}")
gsettings set $SCHEMA custom-keybindings "[$PATHS_STR]"

# Configure each keybinding
for i in "${!BINDINGS[@]}"; do
    IFS=':' read -r KEY CMD <<< "${BINDINGS[$i]}"
    PATH_FULL="$PATH_BASE/quicktile$i/"

    # Convert key to GNOME format
    BINDING="$MODMASK$KEY"

    echo "Setting: $BINDING -> $CMD"

    gsettings set "$CUSTOM_SCHEMA:$PATH_FULL" name "QuickTile: $CMD"
    gsettings set "$CUSTOM_SCHEMA:$PATH_FULL" command "$QUICKTILE $CMD"
    gsettings set "$CUSTOM_SCHEMA:$PATH_FULL" binding "$BINDING"
done

echo ""
echo "Keybindings configured successfully!"
echo "You can test by pressing ${MODMASK}K to move window to left half."
