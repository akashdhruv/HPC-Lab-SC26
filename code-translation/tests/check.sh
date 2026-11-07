#!/usr/bin/env bash
#
# The oracle: clean build, one run, and the diag lines compared with the golden output
# of the original Fortran code. Exit 0 means correct.

set -o pipefail

tests="$(cd "$(dirname "$0")" && pwd)"
app="$tests/../app"
output="$(mktemp)"
trap 'rm -f "$output"' EXIT

# Build from scratch
make -C "$app" clean > /dev/null
if ! make -C "$app" 2>&1 | tail -n 25; then
    echo "FAIL: build"
    exit 1
fi

# Run once
if ! (cd "$app" && timeout 60 ./rd2d) > "$output" 2>&1; then
    tail -n 20 "$output"
    echo "FAIL: run"
    exit 1
fi

# Compare with the golden output
python3 "$tests/compare.py" "$output"
