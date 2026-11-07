#!/usr/bin/env bash
#
# Exit 0 if an item is approved in an instance's approvals.toml; act steps call this first.
#
#   tools/approved.sh <instance> "<item>"

instance="$1"
item="$2"

if grep -q "^item = \"$item\"" "$instance/approvals.toml" 2>/dev/null; then
    exit 0
fi

echo "not approved: '$item' in $instance/approvals.toml"
echo "approve with: tools/approve.sh $instance \"$item\""
exit 1
