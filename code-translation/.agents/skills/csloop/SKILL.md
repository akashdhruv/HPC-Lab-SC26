---
name: csloop
description: Start the CodeScribe loop of an approved transformation in the background (dev/bin/loop -b <name> [loops]).
---

The transformation is checked in: `<name>` is `translate` unless the scientist says otherwise.
Run `dev/bin/loop -b <name> [loops]` once, from `code-translation/`. The loop runs outside this
session (`../tools/loop.py` in `.venv`, model from `config.yaml`). Report whether it started; if it
refused, say why and what the scientist must do. Do not start it again. Follow it later with
`dev/bin/status <name>`.
