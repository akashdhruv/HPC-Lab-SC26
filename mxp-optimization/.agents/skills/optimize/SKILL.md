---
name: optimize
description: Run the optimize stage: plan an OpenEvolve search that makes the raptorized kernel more accurate under RAPTOR's fp8 emulation (decide, calibrate, red-team, approval), then launch it, verify candidates and ask for acceptance. Use for anything about planning, running or reviewing an optimization or search.
---

# optimize (evolutionary search)

The stage contract. Role: make the raptorized kernel as accurate as possible under RAPTOR's
emulation of a low precision, by searching rewrites with OpenEvolve. The objective is
open-ended and no one knows the answer, but a score can be trusted: that is when a search beats
a loop or a session. Instance R: `experiments/<E>/<n>-optimize/`. Precondition: raptorize
accepted in the same E. Commands run from `mxp-optimization/`; everything runs in the container
(`../tools/container`). The harness code is in `scripts/` next to this file (run.py, evaluation.py, animate.py).

## Plan mode

1. `dev/bin/new optimize <same E> [source]` prints R. `source` defaults to `app/src/advect.cpp`;
   pass the raptorized kernel (e.g. `app/src/redistance.cpp`) to target another kernel.
2. Ask (proposing a default for each, explained plainly) and fill R's plan.md (including who
   planned it: your orchestrator and model), experiment.yaml and evaluator.py; match the mode
   and columns raptorize added:

| question | default |
|---|---|
| target | mode `fp8` (RAPTOR, e4m3): the kernel truncated to fp8 matches the original WENO5 in fp64 |
| score | -(mean over steps of `err_shape`): M, the mean distance between the fp8 and fp64 interfaces in cells; raptorize's eval run (64², t = 0.5) |
| guards | equivalence: the candidate's fp64 run reproduces the seed's (1e-10) |
| rules | types stay double, no library calls but min/max/abs, no preprocessor |
| job | models from config.yaml `evolve`, max_programs 10, timeout 300 s |

3. Calibrate: `../tools/container make evaluate EXP=<R>` twice, identical scores; put the seed score
   in the problem. The fp8 seed is NaN (`NAN_OR_INF`, score null): then two identical labels, and
   the search starts from it. The prompt states only rules the evaluator enforces.
4. Red-team: `../tools/container make redteam EXP=<R>`, 0 holes.
5. Show decisions, calibration and red-team; the scientist approves with `../tools/approve <R> plan`.

## Run mode

1. Act: `dev/bin/evolve <R>` starts the search in the detached container
   `hpc-lab-mxp-optimization` (it refuses an unapproved plan or a second search); it outlives
   the session. From any session: `dev/bin/evolve --status <R>` (running or not, scores, log),
   `--stop <R>` ends it, `--resume <R>` continues from the last checkpoint.
2. Verify: `../tools/container make harvest EXP=<R>` (each candidate and its diff against the seed
   in results/candidates/); for the top 3, read the diff and say why the rewrite reduces rounding
   error while staying exact in real arithmetic; re-score the best.
3. Show: `dev/bin/animate <R> <id>` runs fp64, the seed and the candidate in fp8 and writes
   `<R>/results/animation.mp4` (the bubble and its error, seed next to candidate).
4. Acceptance: the scientist records `../tools/approve <R> "candidate <id>"`; then
   `../tools/container make apply EXP=<R> ID=<id>`.

## Checks (the verification boundary)

- Every candidate: rules audited before the build, `make RAPTOR=1`, the fp8 run, the fp64
  equivalence guard; anything else changed outside the block scores null.
- Calibration and red-team before the search; re-score and `make check` before acceptance.

## Boundaries

- May write: R (except approvals.toml); app/ only through `make apply`.
- One search at a time: each evaluation swaps a candidate into app/.
- Never write `approvals.toml` or run `../tools/approve`.

## Provenance

R keeps plan.md, approvals.toml, experiment.yaml, evaluator.py, seed.cpp and results/
(fp64_reference.csv, baseline, redteam.md, evaluations.jsonl, checkpoints, candidates,
animation.mp4).
