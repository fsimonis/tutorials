#!/bin/sh
set -e -u

mpirun -n 4 python3 solver.py Left
