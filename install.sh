#!/bin/sh

cd "$(dirname "$(readlink -f "$0")")"

if [ "$(id -u)" != 0 ]; then
    echo "* Building without elevated privileges"
    python3 setup.py build

    echo "* Acquiring permissions to perform system-wide install"
    exec sudo "$0" "$@"
fi

echo "* Attempting to remove old QuickTile installs"
pip2 uninstall quicktile -y
pip3 uninstall quicktile -y
rm -f /usr/local/bin/quicktile{,.py}

echo "* Running setup.py install"
python3 setup.py install

echo "* Copying quicktile.desktop to /etc/xdg/autostart/"
sudo cp quicktile.desktop /etc/xdg/autostart/
