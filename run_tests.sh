#!/bin/sh

echo "-- MyPy --"
MYPYPATH="quicktile" mypy --strict-optional --ignore-missing-imports quicktile
echo "-- Nose (unit tests) --"
nosetests3 "$@"
echo "-- ePyDoc (documentation syntax) --"
epydoc --config setup.cfg quicktile ./*.py
