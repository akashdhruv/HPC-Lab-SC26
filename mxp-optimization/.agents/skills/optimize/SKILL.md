---
name: optimize
description: Run the optimize stage: plan an OpenEvolve search that makes the raptorized kernel more accurate under RAPTOR's bf16 emulation (decide, calibrate, red-team, approval), then launch it, verify candidates and ask for acceptance. Use for anything about planning, running or reviewing an optimization or search.
---

# optimize (evolutionary search)

The stage contract. Role: make the raptorized kernel as accurate as possible under RAPTOR's
emulation of a low precision, by searching rewrites with OpenEvolve. The objective is
open-ended and no one knows the answer, but a score can be trusted: that is when a search beats
a loop or a session. Instance R: `experiments/<E>/<n>-optimize/`. Precondition: raptorize
accepted in the same E. Commands run from `mxp-optimization/`; everything runs in the container
(`dev/bin/box`). The harness code is in `dev/workflows/optimize/` (run.py, evaluation.py).

## Plan mode

1. `dev/bin/box make run STAGE=optimize E=<same E>` prints R.
2. Ask (proposing a default for each, explained plainly) and fill R's plan.md (including who
   planned it: your orchestrator and model), experiment.yaml and evaluator.py; match the mode
   and columns raptorize added:

| question | default |
|---|---|
| target | mode `bf16` (RAPTOR), the FP64 kernel inside the EVOLVE-BLOCK truncated |
| score | -log10 RMS over steps of `err_rms`, 128², 100 steps |
| guards | equivalence: the candidate's fp64 run reproduces the seed's (1e-10) |
| rules | types stay double, no library calls but min/max/abs, no preprocessor |
| job | models from config.yaml `evolve`, max_programs 10, timeout 300 s |

3. Calibrate: `dev/bin/box make evaluate EXP=<R>` twice, identical scores; put the seed score
   in the problem. The prompt states only rules the evaluator enforces.
4. Red-team: `dev/bin/box make redteam EXP=<R>`, 0 holes.
5. Show decisions, calibration and red-team; the scientist approves with `../tools/approve <R> plan`.

## Run mode

1. Act: `dev/bin/evolve <R>` starts the search in the detached container
   `hpc-lab-mxp-optimization` (it refuses an unapproved plan); progress
   `dev/bin/box make status EXP=<R>`; `docker stop hpc-lab-mxp-optimization` ends it
   (`dev/bin/box make resume EXP=<R>` continues).
2. Verify: `dev/bin/box make harvest EXP=<R>`; for the top 3, the diff against seed.cpp and why
   the rewrite reduces rounding error while staying exact in real arithmetic; re-score the best.
3. Acceptance: the scientist records `../tools/approve <R> "candidate <id>"`; then
   `dev/bin/box make apply EXP=<R> ID=<id>`.

## Checks (the verification boundary)

- Every candidate: rules audited before the build, `make RAPTOR=1`, the bf16 run, the fp64
  equivalence guard; anything else changed outside the block scores null.
- Calibration and red-team before the search; re-score and `make check` before acceptance.

## Boundaries

- May write: R (except approvals.toml); app/ only through `make apply`.
- One search at a time: each evaluation swaps a candidate into app/.
- Never write `approvals.toml` or run `tools/approve`.

## Provenance

R keeps plan.md, approvals.toml, experiment.yaml, evaluator.py, seed.cpp and results/
(fp64_reference.csv, baseline, redteam.md, evaluations.jsonl, checkpoints, candidates).
