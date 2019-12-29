#!/bin/bash

echo "-- MyPy --"
MYPYPATH="quicktile" mypy quicktile ./*.py functional_harness
echo "-- Nose (unit tests) --"
nosetests3 "$@"
echo "-- ePyDoc (documentation syntax) --"
epydoc --config setup.cfg quicktile ./*.py functional_harness 2> >(grep -v 'Invalid -W option ignored' >&2)
