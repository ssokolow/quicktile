#!/bin/sh

if [ "$(id -u)" != 0 ]; then
    echo "* Building without elevated privileges"
    python2 setup.py build

    echo "* Acquiring permissions to perform system-wide install"
    exec sudo "$0" "$@"
fi

echo "* Running setup.py install"
python2 setup.py install

echo "* Copying quicktile.desktop to /etc/xdg/autostart/"
sudo cp quicktile.desktop /etc/xdg/autostart/
