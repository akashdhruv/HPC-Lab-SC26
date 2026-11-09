# code-translation

An agent system (Translation thrust): Fortran -> C++ for `app/`, rd2d, a Gray-Scott
reaction-diffusion mini-app of 13 Fortran units. Stage: translate, an autonomous loop. Its tools:
`dev/README.md` (class `Translation(Lab)` in `dev/tools.py`); the interface an application must
meet: `dev/app.md`.

Agents run natively; everything that builds or runs the app runs in the `hpc-lab-translate`
container through its tools: `dev/bin/oracle` (app/tests/check.sh), `dev/bin/readiness`
(dev/tools/index.py), `dev/bin/build` (make -C app), and the inherited
`../tools/container <command>`. Never call make, gfortran or g++ directly.

The transformation is checked in: `transformations/app-translate/` (desired_spec.md,
current_plan.md, loop.toml: 13 units in 4 groups). Its plan is the stage's plan mode, already
written; the scientist reviews and approves it.

    approve the plan  ->  loop  ->  loop-status (verify)  ->  accept the group  ->  loop ...
    scientist            agent        agent                      scientist

- `../tools/approve transformations/app-translate plan`, then `"Group <k>"`: scientist only.
- `dev/bin/loop <name> [loops]`: the autonomous loop (`dev/tools/loop.py`, this system's harness,
  on CodeScribe in `.venv`, model from config.yaml), detached from the session; it refuses an
  unapproved plan or a second copy and stops at the end of a group. `-f` runs it in the
  foreground, `--stop` stops it. Its log: `transformations/<name>/runs/loop.log`.
- `dev/bin/status [name]`: approvals, groups, agent log, the loop (running or not, its log, its
  last runs).
- Skills: `loop` (asks which transformation, then starts it), `loop-status` (report, and verify
  a stopped loop).
- The loop writes `app/src` and `agent_log.md`; the harness reverts any change to the spec,
  plan, approvals, `loop.toml`, `app/tests/`, `app/Makefile` and `app/include/`. Each run is
  recorded in `transformations/app-translate/runs/<run_id>/`. `git checkout app/` starts over.
