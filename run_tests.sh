#!/bin/bash

cd -- "$(dirname -- "$(readlink -f -- "$0")")" || exit 1
echo "-- MyPy --"
mypy --exclude=build --warn-unused-ignores .
echo " -- Ruff (static analysis) --"
ruff check .
echo "-- Nose (unit tests) --"
nosetests3 "$@"
echo "-- Sphinx (documentation syntax) --"
cd docs || exit 1
make coverage | grep -v 'Testing of coverage in the sources finished'
cat _build/coverage/python.txt
