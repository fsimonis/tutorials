#!/bin/sh
set -e -u

mpirun -n 9 python3 solver.py Right
