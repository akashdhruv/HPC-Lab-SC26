---
name: optimize
description: Run the optimize stage: plan an OpenEvolve search that makes the raptorized kernel more accurate under RAPTOR's bf16 emulation (decide, calibrate, red-team, approval), then launch it, verify candidates and ask for acceptance. Use for anything about planning, running or reviewing an optimization or search.
---

# optimize (evolutionary search)

Read `dev/workflows/optimize/system.md`. The kernel must be raptorized first (an accepted
raptorize run in the same experiment). Everything runs in the container (`dev/bin/box`).

## Plan mode

1. `dev/bin/box make run STAGE=optimize E=<same E>` prints R.
2. Ask the contract's questions with defaults, explain each plainly, write R's plan.md,
   experiment.yaml and evaluator.py (match the mode and columns raptorize added).
3. Calibrate: `dev/bin/box make evaluate EXP=<R>` twice, identical; put the seed score in the problem.
4. Red-team: `dev/bin/box make redteam EXP=<R>`, 0 holes.
5. Show decisions, calibration and red-team; ask for approval: `/approve <R> plan`.

## Run mode

1. `/evolve <R>`; `/evolve-status <R>` when asked.
2. When it ends: `dev/bin/box make harvest EXP=<R>`; for the top 3, the diff against seed.cpp
   and one line on why the rewrite reduces rounding error while staying exact; re-score the best.
3. The scientist accepts with `/approve <R> "candidate <id>"`; then
   `dev/bin/box make apply EXP=<R> ID=<id>`.

Never write approvals.toml.
