#!/usr/bin/env bash
# The OpenEvolve search of an optimize run, inside the detached container (dev/bin/evolve).
# Its output is appended to <R>/results/evolve.log.
#
#   dev/tools/search.sh <R> [evolve|resume]

run=$1
action=${2:-evolve}
python=${PY:-python3}

mkdir -p "$run/results"
exec "$python" .agents/skills/optimize/scripts/run.py "$action" "$run" >> "$run/results/evolve.log" 2>&1
