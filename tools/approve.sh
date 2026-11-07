#!/usr/bin/env bash
#
# Record a human approval in an instance's approvals.toml.
#
#   tools/approve.sh <instance> "<item>" ["note"]
#
# Items: "plan", then "Group <k>" (translation) or "candidate <id>" (optimization).

set -euo pipefail

instance="${1:?usage: approve.sh <instance> \"<item>\" [\"note\"]}"
item="${2:?missing item, e.g. plan}"
note="${3:-}"
file="$instance/approvals.toml"

if [ ! -f "$file" ]; then
    echo "no $file"
    exit 1
fi

cat <<TOML | tee -a "$file"

[[approved]]
item = "$item"
by = "${USER:-human}"
date = "$(date +%F)"
note = "$note"
TOML
