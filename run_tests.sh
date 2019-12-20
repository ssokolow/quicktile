#!/bin/bash

echo "-- MyPy --"
MYPYPATH="quicktile" mypy --strict-optional --ignore-missing-imports quicktile
echo "-- Nose (unit tests) --"
nosetests3 "$@"
echo "-- ePyDoc (documentation syntax) --"
epydoc --config setup.cfg quicktile ./*.py 2> >(grep -v 'Invalid -W option ignored' >&2)
