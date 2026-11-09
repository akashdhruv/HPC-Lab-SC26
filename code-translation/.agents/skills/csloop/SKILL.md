---
name: csloop
description: Start the CodeScribe loop of an approved transformation detached from the session (dev/bin/loop <name> [loops]).
---

The transformation is checked in: `<name>` is `translate` unless the scientist says otherwise.
Run `dev/bin/loop <name> [loops]` once, from `code-translation/`. The loop runs detached from this
session (`../tools/loop.py` in `.venv`, model from `config.yaml`), so the session may close while it
runs. Report whether it started; if it refused (unapproved plan, already running), say why and
what the scientist must do. Do not start it again. Follow it later, from any session, with
`dev/bin/status <name>`; `dev/bin/loop --stop <name>` stops it, only when the scientist asks.
