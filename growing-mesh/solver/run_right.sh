#!/bin/sh
set -e -u

if [ $# -eq 0 ]; then
  python3 solver.py Right
else
  mpirun -n $@ python3 solver.py Right
fi
