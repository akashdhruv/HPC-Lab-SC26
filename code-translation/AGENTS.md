# code-translation

An agent system (Translation thrust): Fortran -> C++ for `app/`, rd2d, a Gray-Scott
reaction-diffusion mini-app of 13 Fortran units. Stage: translate, an autonomous loop. The
interface an application must meet: `dev/app.md`.

Agents run natively; everything that builds or runs the app runs in the `hpc-lab-translate`
container through `dev/bin/`: `oracle` (tests/check.sh), `readiness` (dev/tools/index.py),
`build` (make -C app), `container <command>`. Never call make, gfortran or g++ directly.

The transformation is checked in: `dev/transformations/translate/` (desired_spec.md,
current_plan.md, loop.toml: 13 units in 4 groups). Its plan is the stage's plan mode, already
written; the scientist reviews and approves it.

    approve the plan  ->  csloop  ->  csloop-status (verify)  ->  accept the group  ->  csloop ...
    scientist            agent        agent                      scientist

- `../tools/approve dev/transformations/translate plan`, then `"Group <k>"`: scientist only.
- `dev/bin/loop translate`: the autonomous loop (`../tools/loop.py` on CodeScribe in `.venv`,
  model from config.yaml), detached from the session; it refuses an unapproved plan or a second
  copy and stops at the end of a group. `-f` runs it in the foreground, `--stop` stops it.
- `dev/bin/status [translate]`: approvals, groups, agent log, the loop (running or not, its log,
  its last runs).
- Skills: `csloop` (start the loop), `csloop-status` (report, and verify a stopped loop).
- The loop writes `app/src` and `agent_log.md`; the harness reverts any change to the spec,
  plan, approvals, `loop.toml`, `tests/`, `app/Makefile` and `app/include/`. Each run is
  recorded in `dev/transformations/translate/runs/<run_id>/`. `git checkout app/` starts over.
