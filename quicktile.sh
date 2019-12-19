#!/bin/sh
cd "$(dirname "$(readlink -f "$0")")"
exec python3 -m quicktile "$@"
