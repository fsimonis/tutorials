#!/bin/sh
set -e -u

python3 -m venv .venvl
. .venvl/bin/activate
pip install -r requirements.txt

if [ $# -eq 0 ]; then
  python3 solver.py Left
else
  mpirun -n "$@" python3 solver.py Left
fi
