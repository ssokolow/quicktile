#!/bin/sh
cd "$(dirname "$(readlink -f "$0")")"
python2 -m quicktile "$@"
