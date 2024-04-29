#!/bin/bash
set -e -u

. ../../tools/log.sh
exec > >(tee --append "$LOGFILE") 2>&1

usage() { echo "Usage: cmd [-s] [-p n]" 1>&2; exit 1; }

# Check if no input argument was provided
if [ -z "$*" ] ; then
  echo "No input argument provided. Micro Manager is launched in serial"
  micro_manager micro-manager-config.json
fi

while getopts ":sp" opt; do
  case ${opt} in
  s)
    micro_manager micro-manager-config.json
    ;;
  p)
    mpiexec -n "$2" micro_manager micro-manager-config.json
    ;;
  *)
    usage
    ;;
  esac
done

close_log
