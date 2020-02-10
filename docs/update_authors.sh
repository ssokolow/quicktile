#!/bin/sh

TMP_TARGET="_build/authors"

cd "$(dirname "$(readlink -f "$0")")"

rm -rf "$TMP_TARGET/index.txt"
sphinx-build -b text -c . authors "$TMP_TARGET"
mv $TMP_TARGET/index.txt ../AUTHORS
