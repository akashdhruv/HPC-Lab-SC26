---
name: loop
description: Start the system's loop (dev/tools/loop.py) on an approved transformation, detached from the session (dev/bin/loop <name> [loops]); always asks the scientist which transformation first.
---

Always ask the scientist which transformation to run, even if only one exists or one was named
earlier: list the folders of `transformations/` and wait for the answer. Never assume `<name>`.
Ask for the number of loops only if the scientist wants other than 10.

Then run `dev/bin/loop <name> [loops]` once, from `code-translation/`. The loop runs detached from
this session (`dev/tools/loop.py` in `.venv`, model from `config.yaml`), so the session may
close while it runs. Report whether it started; if it refused (unapproved plan, already running),
say why and what the scientist must do. Do not start it again. Follow it later, from any session,
with `dev/bin/status <name>`; `dev/bin/loop --stop <name>` stops it, only when the scientist asks.
