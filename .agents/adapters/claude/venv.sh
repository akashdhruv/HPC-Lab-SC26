#!/bin/sh
# SessionStart hook: puts the tutorial's .venv first on PATH for Claude Code's commands.
# With orchestrator.dev_bin_on_path in config.yaml, the stub folders go before it:
# the session's system dev/bin, then tools/ (tools/hpclab.py prints them).

session=$PWD
cd "$(git rev-parse --show-toplevel)" || exit 0
[ -n "$CLAUDE_ENV_FILE" ] || exit 0

python=.venv/bin/python
[ -x "$python" ] || python=.venv/Scripts/python.exe

stubs=""
for folder in $("$python" tools/hpclab.py bins "$session" 2>/dev/null); do
    stubs="$stubs$PWD/$folder:"
done

echo "export VIRTUAL_ENV=\"$PWD/.venv\"" >> "$CLAUDE_ENV_FILE"
echo "export PATH=\"$stubs$PWD/.venv/bin:$PWD/.venv/Scripts:\$PATH\"" >> "$CLAUDE_ENV_FILE"
