#!/bin/bash
# Run QuickTile from source directory
cd "$(dirname "$0")"
exec python3 -m quicktile "$@"
