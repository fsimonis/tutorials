#!/bin/sh
set -e -u

python3 -m venv .venv
. .venv/bin/activate
pip install ../solver

if [ $# -eq 0 ]; then
  growing B
else
  mpirun -n "$@" growing B
fi
