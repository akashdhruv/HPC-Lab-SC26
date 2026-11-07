#!/usr/bin/env bash
#
# Author -> oracle -> reviewer loop on a transformation, each phase a fresh pi session.
# It iterates until the group is complete, the oracle passes and the review is clean.
# The rules come from the same loop.toml CodeScribe reads; .pi/extensions/guard.ts
# enforces them.
#
#   dev/tools/pi-loop.sh [-b] <name> [max_loops]
#
# -b runs it in the background; everything goes to <transformation>/runs/loop.log.

set -uo pipefail
cd "$(dirname "$0")/../.."

background=false
if [ "${1:-}" = "-b" ]; then
    background=true
    shift
fi

name="${1:?usage: pi-loop.sh [-b] <name> [max_loops]}"
max_loops="${2:-10}"
task="dev/transformations/$name"
runs="$task/runs"

../tools/approved.sh "$task" plan || exit 1
mkdir -p "$runs"

if $background; then
    nohup "$0" "$name" "$max_loops" > /dev/null 2>&1 &
    echo "loop started, log: $runs/loop.log"
    exit 0
fi

exec > >(tee -a "$runs/loop.log") 2>&1

export PATH="$PWD/dev/bin:$PATH"
export SC26_TASK="$task/loop.toml"

prompt=$(sed -n "/content = '''/,/'''/p" "$SC26_TASK" | sed '1d;$d')
check=$(sed -n '/^\[check\]/,/^\[/ s/^command *= *"\(.*\)"/\1/p' "$SC26_TASK")

agent() {
    pi --approve --no-session --model sc26/agent -p "$@"
}

author() {
    local loop="$1"
    local review
    review=$(cat "$runs/review.md" 2>/dev/null || echo "none yet")

    SC26_ROLE=author agent "$prompt

Loop $loop of $max_loops. Latest review ($runs/review.md):
$review

End with a line: STATUS: COMPLETE or STATUS: INCOMPLETE."
}

reviewer() {
    local loop="$1"
    local status="$2"

    SC26_ROLE=review agent --tools read,bash "You review loop $loop of $task.

Read its desired_spec.md and current_plan.md. The author's report is $runs/$loop-author.md;
the oracle's output is $runs/$loop-check.txt (exit $status). Do not trust the report: use
git status, git diff and the changed files. Check the unit settled in this loop against the
Spec's rules and silent traps, and whether the group is really complete.

List concrete defects or missing work, one per line, for the next author session.
End with a line: VERDICT: CLEAN or VERDICT: ISSUES."
}

for loop in $(seq 1 "$max_loops"); do
    echo "== $(date +%T) loop $loop/$max_loops: author"
    author "$loop" > "$runs/$loop-author.md"
    tail -n 3 "$runs/$loop-author.md"

    echo "== $(date +%T) loop $loop/$max_loops: oracle ($check)"
    eval "$check" > "$runs/$loop-check.txt" 2>&1
    status=$?
    tail -n 1 "$runs/$loop-check.txt"

    echo "== $(date +%T) loop $loop/$max_loops: reviewer"
    reviewer "$loop" "$status" > "$runs/$loop-review.md"
    cp "$runs/$loop-review.md" "$runs/review.md"
    tail -n 3 "$runs/$loop-review.md"

    complete=$(grep -c "STATUS: COMPLETE" "$runs/$loop-author.md")
    clean=$(grep -c "VERDICT: CLEAN" "$runs/$loop-review.md")
    if [ "$status" = 0 ] && [ "$complete" -gt 0 ] && [ "$clean" -gt 0 ]; then
        echo "== stop: group complete, oracle passes, review clean"
        exit 0
    fi
done

echo "== stop: max_loops reached"
