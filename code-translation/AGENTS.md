# code-translation

An agent system (Translation thrust): Fortran -> C++ for `app/`, rd2d, a Gray-Scott
reaction-diffusion mini-app of 13 Fortran units. Stage: translate (skill
`.agents/skills/translate/SKILL.md`). The interface an application must meet: `dev/app.md`.

Agents run natively; everything that builds or runs the app runs in the `hpc-lab-translate`
container through `dev/bin/`: `oracle` (tests/check.sh), `readiness` (dev/tools/index.py),
`build` (make -C app), `box <command>`. Never call make, gfortran or g++ directly.

- `dev/bin/loop [-b] <name>`: the autonomous loop (CodeScribe's harness, model from config.yaml).
- `dev/bin/status [name]`: approvals, groups, agent log, loop runs.
- `dev/transformations/<name>/`: one folder per transformation, its provenance record.
- pi commands (shortcuts for the lines above): /readiness /check /approve /loop /status.
