#!/usr/bin/env bash
#
# Save app/'s changes since HEAD as one patch, untracked files included (raptorize checkpoints).
# Runs natively with git; the real index is never touched.
#
#   dev/tools/patch.sh <R>/patches/<k>-<name>.patch

set -euo pipefail
cd "$(dirname "$0")/../.."

out="${1:?usage: patch.sh <file>}"
index="$(mktemp)"
trap 'rm -f "$index"' EXIT

export GIT_INDEX_FILE="$index"
git read-tree HEAD
git add -A app
git diff --cached --binary HEAD -- app > "$out"
echo "saved $out"
