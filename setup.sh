#!/usr/bin/env sh
# One-time setup; the same as tools/setup (on cmd.exe or PowerShell: tools\setup).
cd "$(dirname "$0")" && exec tools/setup "$@"
