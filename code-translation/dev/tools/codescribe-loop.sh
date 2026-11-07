#!/usr/bin/env bash
#
# Run a transformation with the CodeScribe loop instead of pi; same loop.toml. CodeScribe and
# its model calls run natively; builds and the oracle run in the container (dev/bin).
#
#   dev/tools/codescribe-loop.sh [-b] <name> [code-scribe options, e.g. -nloop 6 -v]
#
# -b runs it in the background; output goes to <transformation>/runs/codescribe.log.

set -euo pipefail
cd "$(dirname "$0")/../.."

background=false
if [ "${1:-}" = "-b" ]; then
    background=true
    shift
fi

name="${1:?usage: codescribe-loop.sh [-b] <name> [options]}"
shift
task="dev/transformations/$name"

../tools/approved.sh "$task" plan
mkdir -p "$task/runs"

if $background; then
    nohup "$0" "$name" "$@" > "$task/runs/codescribe.log" 2>&1 &
    echo "codescribe started, log: $task/runs/codescribe.log"
    exit 0
fi

python=$(command -v python3 || command -v python)
eval "$("$python" ../tools/endpoint.py)"
export PATH="$PWD/dev/bin:$PATH"

codescribe=code-scribe
for candidate in ../.venv/bin/code-scribe ../.venv/Scripts/code-scribe.exe; do
    if [ -x "$candidate" ]; then
        codescribe="$candidate"
    fi
done

echo "[codescribe] $task/loop.toml with $MODEL"
exec "$codescribe" loop "$task/loop.toml" -m "$MODEL" --log "$@"
