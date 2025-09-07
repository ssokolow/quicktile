#!/bin/bash

cd -- "$(dirname -- "$(readlink -f -- "$0")")" || exit 1
(
    echo "--== Sphinx (documentation syntax) ==--"
    cd docs || exit 1
    make -s SPHINXOPTS=-q coverage | grep -v '+--------------------------------+----------+--------------+'
    echo "--== Sphinx (doctests) ==--"
    make -s doctest
)
echo "--== MyPy ==--"
mypy --exclude=build --warn-unused-ignores .
echo " --== Ruff (static analysis) ==--"
ruff check .
echo "--== PyTest (unit tests) ==--"
python3 -m pytest "$@"
