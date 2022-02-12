#!/bin/bash

cd "$(dirname "$(readlink -f "$0")")"
echo "-- MyPy --"
MYPYPATH="quicktile" mypy --config-file=setup.cfg quicktile ./*.py functional_harness
echo " -- Flake8 (static analysis) --"
python3 -m flake8 --config=setup.cfg quicktile/ ./*.py functional_harness
echo "-- Nose (unit tests) --"
nosetests3 "$@"
echo "-- Sphinx (documentation syntax) --"
cd docs
make coverage | grep -v 'Testing of coverage in the sources finished'
cat _build/coverage/python.txt
