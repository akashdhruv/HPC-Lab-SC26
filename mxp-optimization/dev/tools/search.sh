#!/usr/bin/env bash
#
# The OpenEvolve search of a run, inside the detached container (dev/bin/evolve); output appended
# to <R>/results/evolve.log.
#
#   dev/tools/search.sh <R> [evolve|resume]

mkdir -p "$1/results"
exec "${PY:-python3}" .agents/skills/optimize/scripts/run.py "${2:-evolve}" "$1" >> "$1/results/evolve.log" 2>&1
