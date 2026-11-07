---
name: translate
description: Translate the Fortran of app/ to C++. Plan mode writes a transformation (spec, plan, loop.toml) into dev/transformations/<name>/ for approval; run mode starts the author/reviewer loop, verifies the result and asks for acceptance. Use for anything about planning, running or checking a translation.
---

# translate

A transformation is a folder `dev/transformations/<name>/` made from `templates/` (next to this
file). A loop (pi or CodeScribe) reads its `loop.toml`, settles one unit per iteration, and
stops when a group is complete, the oracle passes and the review is clean.

## Plan mode

1. Run `dev/bin/readiness` and `dev/bin/oracle` (both in the container); the oracle must pass.
2. Propose, with a default for each, and let the scientist adjust:
   - name: kebab-case, a new folder;
   - scope: all units in `app/src`;
   - groups: 2-4 units each, in readiness order (later units may become ready as earlier units
     of the same group are translated);
   - runner: `/loop <name>` (pi); `/codescribe <name>` to compare.
3. Copy `templates/*` into `dev/transformations/<name>/` and fill every `<...>`. Do not change
   the rules: they are the contract.
4. Show the folder; the scientist approves with `/approve <name> plan`.

## Run mode

1. Act: `/loop <name>` (or `/codescribe <name>`); it refuses an unapproved plan. Follow it with
   `/status <name>` or `runs/loop.log`.
2. Verify when it stops: `dev/tools/status.sh <name>`, `dev/bin/oracle`, `dev/bin/readiness`,
   `git status --short app/`. Every `verified` line in
   `agent_log.md` must be a unit now in C++ with its `.F90` gone. Spot-check one unit against
   the spec's rules and traps, and quote the lines.
3. Recommend: a table unit | status | evidence | your check, then "accept Group <k>" or what to
   fix. The scientist accepts with `/approve <name> "Group <k>"`; the next `/loop` starts the
   next group.

## Boundaries

- Write only the new transformation folder (plan mode). The loop writes `app/src` and
  `agent_log.md`; `.pi/extensions/guard.ts` protects the spec, plan, approvals and `tests/`.
- Never write `approvals.toml`.
