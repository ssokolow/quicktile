#!/bin/bash

cd "$(dirname "$(readlink -f "$0")")"
echo "-- MyPy --"
MYPYPATH="quicktile" mypy quicktile ./*.py functional_harness
echo "-- Nose (unit tests) --"
nosetests3 "$@"
echo "-- Doctests (util.py) --"
python3 -m doctest quicktile/util.py
echo "-- Sphinx (documentation syntax) --"
cd docs
make coverage
cat _build/coverage/python.txt
