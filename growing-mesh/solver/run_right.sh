#!/bin/sh
set -e -u

python3 -m venv .venvr
. .venvr/bin/activate
pip install -r requirements.txt

if [ $# -eq 0 ]; then
  python3 solver.py Right
else
  mpirun -n "$@" python3 solver.py Right
fi
