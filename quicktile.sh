#!/bin/sh
cd -- "$(dirname -- "$(readlink -f -- "$0")")" || exit 1
exec python3 -m quicktile "$@"
