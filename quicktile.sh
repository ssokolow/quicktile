#!/bin/sh
cd "$(dirname "$(readlink -f "$0")")"
python3 -m quicktile "$@"
