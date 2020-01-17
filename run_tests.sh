#!/bin/bash

echo "-- MyPy --"
MYPYPATH="quicktile" mypy quicktile ./*.py functional_harness
echo "-- Nose (unit tests) --"
nosetests3 "$@"
echo "-- Sphinx (documentation syntax) --"
cd docs
make html
