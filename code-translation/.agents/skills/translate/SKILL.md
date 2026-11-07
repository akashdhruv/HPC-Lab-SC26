---
name: translate
description: Translate the Fortran of app/ to C++. Plan mode writes a transformation (spec, plan, loop.toml) into dev/transformations/<name>/ for approval; run mode starts the CodeScribe author/check/review loop, verifies the result and asks for acceptance. Use for anything about planning, running or checking a translation.
---

# translate (autonomous loop)

The stage contract of code-translation. A transformation is a folder `dev/transformations/<name>/`
made from `templates/` (next to this file). `dev/bin/loop` runs CodeScribe's author -> check ->
review harness on its `loop.toml`: one unit per author session, the oracle after every session,
stop when the group is complete, the oracle passes and the review is clean. The harness calls
the model in `config.yaml` and enforces `loop.toml` itself, so the loop is the same under any
orchestrator. Commands run from `code-translation/`.

## Plan mode

1. Run `dev/bin/readiness` and `dev/bin/oracle` (both in the container); the oracle must pass.
2. Propose, with a default for each, and let the scientist adjust:
   - name: kebab-case, a new folder;
   - scope: all units in `app/src`;
   - groups: 2-4 units each, in readiness order (later units may become ready as earlier units
     of the same group are translated);
   - loops per run: 10.
3. Copy `templates/*` into `dev/transformations/<name>/` and fill every `<...>`, including who
   planned it (your orchestrator and model). Do not change the rules: they are the contract.
4. Show the folder; the scientist approves with `../tools/approve dev/transformations/<name> plan`.

## Run mode

1. Act: `dev/bin/loop -b <name>`; it refuses an unapproved plan. Follow it with
   `dev/bin/status <name>` or `dev/transformations/<name>/runs/loop.log`.
2. Verify when it stops: `dev/bin/status <name>`, `dev/bin/oracle`, `dev/bin/readiness`,
   `git status --short app/`. Every `verified` line in `agent_log.md` must be a unit now in C++
   with its `.F90` gone. Spot-check one unit against the spec's rules and traps, and quote the lines.
3. Recommend: a table unit | status | evidence | your check, then "accept Group <k>" or what to
   fix. The scientist accepts with `../tools/approve dev/transformations/<name> "Group <k>"`;
   the next `dev/bin/loop` starts the next group.

## Checks (the verification boundary)

- `dev/bin/oracle` (`tests/check.sh`): clean build, one run, every `diag` number within rtol
  1e-12 of the original Fortran's output. The harness runs it after every author session; its
  exit code, not the author's report, decides.

## Boundaries

- Plan mode writes only the new transformation folder. The loop writes `app/src` and
  `agent_log.md`; the harness reverts any change to the spec, plan, approvals, `loop.toml`,
  `tests/`, `app/Makefile` and `app/include/`.
- Never write `approvals.toml` or run `tools/approve`.

## Provenance

`dev/transformations/<name>/` keeps desired_spec.md, current_plan.md, loop.toml,
approvals.toml and agent_log.md; `runs/<run_id>/` keeps the harness's record of each loop run
(run.toml with model, tokens and stop reason, rules.toml, metadata/, host.toml) and `runs/loop.log`.
