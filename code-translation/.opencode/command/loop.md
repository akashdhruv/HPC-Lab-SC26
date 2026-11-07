---
description: Start the CodeScribe loop of a transformation in the background (dev/bin/loop -b)
---
!`dev/bin/loop -b $ARGUMENTS`

The loop above runs outside this session (tools/loop.py in .venv, model from config.yaml). Report
whether it started; if it refused, say why and what the scientist must do. Do not start it again.
Follow it later with `dev/bin/status`.
