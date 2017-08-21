#!/bin/sh

epydoc --config setup.cfg quicktile *.py
nosetests
MYPYPATH="quicktile" mypy --py2 --strict-optional --ignore-missing-imports quicktile
