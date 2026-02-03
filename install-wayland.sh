#!/bin/bash
# QuickTile Wayland/GNOME Installer
# Usage: curl -fsSL https://raw.githubusercontent.com/ssokolow/quicktile/master/install-wayland.sh | bash

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_step() { echo -e "${GREEN}[*]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[!]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

is_interactive() { [ -t 0 ]; }

ask() {
    local prompt="$1" default="$2" response
    if is_interactive; then
        read -p "$prompt [$default]: " response
        echo "${response:-$default}"
    else
        echo "$default"
    fi
}

ask_yn() {
    local prompt="$1" default="$2" response
    if is_interactive; then
        read -p "$prompt [${default}]: " response
        response="${response:-$default}"
        [[ "$response" =~ ^[Yy] ]]
    else
        [[ "$default" =~ ^[Yy] ]]
    fi
}

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  QuickTile Wayland/GNOME Installer${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# Check session type
if [ "$XDG_SESSION_TYPE" != "wayland" ] && [ -z "$WAYLAND_DISPLAY" ]; then
    print_warning "This installer is for Wayland. For X11, use: pip3 install quicktile"
    if ! ask_yn "Continue anyway?" "n"; then
        exit 0
    fi
fi

# Install dependencies
print_step "Installing system dependencies..."
if command -v apt &> /dev/null; then
    sudo apt update
    sudo apt install -y python3 python3-pip python3-setuptools python3-gi \
        python3-xlib python3-dbus gir1.2-glib-2.0 gir1.2-gtk-3.0 gir1.2-wnck-3.0 \
        pipx git
elif command -v dnf &> /dev/null; then
    sudo dnf install -y python3 python3-pip python3-setuptools python3-gobject \
        python3-xlib python3-dbus gtk3 libwnck3 pipx git
elif command -v pacman &> /dev/null; then
    sudo pacman -S --noconfirm python python-pip python-setuptools python-gobject \
        python-xlib python-dbus gtk3 libwnck3 python-pipx git
else
    print_error "Unsupported package manager. Install dependencies manually."
    exit 1
fi

pipx ensurepath 2>/dev/null || true

# Check Window Calls extension
print_step "Checking for Window Calls GNOME extension..."
if gnome-extensions list 2>/dev/null | grep -q "window-calls@domandoman.xyz"; then
    print_step "Window Calls extension found."
else
    print_warning "Window Calls extension not found!"
    echo "Install from: https://extensions.gnome.org/extension/4724/window-calls/"
    if is_interactive; then
        read -p "Press Enter after installing..."
    else
        exit 1
    fi
fi

# Clone QuickTile
INSTALL_DIR="$HOME/.local/src/quicktile"
print_step "Installing QuickTile to $INSTALL_DIR..."
mkdir -p "$HOME/.local/src"

if [ -d "$INSTALL_DIR" ]; then
    print_warning "Directory exists. Updating..."
    cd "$INSTALL_DIR" && git pull || true
else
    git clone https://github.com/ssokolow/quicktile.git "$INSTALL_DIR"
fi

# Install with pipx
print_step "Installing with pipx..."
pipx uninstall quicktile 2>/dev/null || true
pipx install "$INSTALL_DIR" --system-site-packages

# Configuration
echo ""
COLUMN_COUNT=$(ask "Number of columns for tiling" "6")
MOD_MASK=$(ask "Modifier keys" "<Ctrl><Alt>")

CONFIG_FILE="$HOME/.config/quicktile.cfg"
print_step "Generating $CONFIG_FILE..."
mkdir -p "$HOME/.config"
cat > "$CONFIG_FILE" << EOF
[general]
cfg_schema = 1
ColumnCount = $COLUMN_COUNT
UseWorkarea = True
ModMask = $MOD_MASK
MovementsWrap = True

[keys]
C = move-to-center
F = fullscreen
V = vertical-maximize
H = horizontal-maximize
Up = maximize
Down = minimize
B = bordered
K = left
L = center
ntilde = right
semicolon = right
I = top-left
O = top
P = top-right
slash = bottom-right
comma = bottom-left
period = bottom
EOF

# Setup keybindings
if ask_yn "Configure GNOME keybindings now?" "y"; then
    bash "$INSTALL_DIR/setup-wayland-keybindings.sh"
fi

echo ""
echo -e "${GREEN}Installation complete!${NC}"
echo ""
echo "Keybindings (${MOD_MASK} + key):"
echo "  K/L/Ñ  - Left / Center / Right"
echo "  I/O/P  - Top corners and top"
echo "  ,/./   - Bottom corners and bottom"
echo "  V/H    - Vertical/Horizontal maximize"
echo ""
echo "Reconfigure: $INSTALL_DIR/setup-wayland-keybindings.sh"
