#!/usr/bin/env bash
#
# State of a transformation: approvals, groups, agent log, and the last loop output.
#
#   dev/tools/status.sh [name]

cd "$(dirname "$0")/../.."

name="${1:-$(ls dev/transformations | head -n 1)}"
if [ -z "$name" ]; then
    echo "no transformation yet: run the translate skill in plan mode"
    exit 0
fi

task="dev/transformations/$name"

echo "== approved"
grep '^item' "$task/approvals.toml" || echo "nothing"

echo "== groups"
grep '^- Group' "$task/current_plan.md"

echo "== agent log"
tail -n 6 "$task/agent_log.md" 2>/dev/null || echo "empty"

echo "== pi loop"
tail -n 6 "$task/runs/loop.log" 2>/dev/null || echo "not run"

echo "== codescribe"
grep -hE '^(loop_index|phase|stop_reason) ' .codescribe/loop/*.toml 2>/dev/null || echo "not run"
