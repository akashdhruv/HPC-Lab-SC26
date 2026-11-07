#!/bin/sh
# SessionStart hook: the tutorial's .venv first on PATH for Claude Code's commands (entry points make and activate it themselves).
cd "$(git rev-parse --show-toplevel)" && [ -n "$CLAUDE_ENV_FILE" ] || exit 0
echo "export VIRTUAL_ENV=\"$PWD/.venv\" PATH=\"$PWD/.venv/bin:$PWD/.venv/Scripts:\$PATH\"" >> "$CLAUDE_ENV_FILE"
