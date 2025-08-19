#!/bin/bash

cd -- "$(dirname -- "$(readlink -f -- "$0")")" || exit 1

if [ "$1" != "-y" ]; then
    echo "This installation process is deprecated because it can pull in packages"
    echo "which mess with your system Python install if you didn't manually"
    echo "install the system version first."
    echo ""
    echo "Press Enter to continue or Ctrl+C to cancel..."
    read -r _FOO
fi

if [ "$(id -u)" != 0 ]; then
    echo "* Building without elevated privileges"
    python3 setup.py build

    echo "* Acquiring permissions to perform system-wide install"
    exec sudo -H "$0" -y "$@"
fi

echo "* Attempting to remove old QuickTile installs"
pip2 uninstall quicktile -y
pip3 uninstall quicktile --break-system-packages -y
rm -f /usr/local/bin/quicktile{,.py}

echo "* Running setup.py install"
python3 setup.py install

echo "* Copying quicktile.desktop to /etc/xdg/autostart/"
sudo cp quicktile/quicktile.desktop /etc/xdg/autostart/
