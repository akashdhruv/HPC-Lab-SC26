#!/usr/bin/env bash
#
# The OpenEvolve search of a run, inside the container; output in <R>/results/evolve.log.
#
#   dev/bin/container -d dev/tools/search.sh <R>

exec "${PY:-python3}" dev/workflows/optimize/run.py evolve "$1" > "$1/results/evolve.log" 2>&1
