# Stage contract: optimize (evolutionary search)

Role: make the raptorized kernel as accurate as possible under RAPTOR's emulation of a low
precision, by searching rewrites with OpenEvolve. The objective is open-ended and no one knows
the answer, but a score can be trusted: that is when a search beats a loop or a session.
Instance R: `experiments/<E>/<n>-optimize/`. Precondition: raptorize accepted in the same E.

## Plan mode

The agent asks (proposing a default for each) and fills R's plan.md, experiment.yaml, evaluator.py:

| question | default |
|---|---|
| target | mode `bf16` (RAPTOR), the FP64 kernel inside the EVOLVE-BLOCK truncated |
| score | -log10 RMS over steps of `err_rms`, 128², 100 steps |
| guards | equivalence: the candidate's fp64 run reproduces the seed's (1e-10) |
| rules | types stay double, no library calls but min/max/abs, no preprocessor |
| job | models from config.yaml `evolve`, max_programs 10, timeout 300 s |

Evidence for approval, in the container: calibrate (`dev/bin/box make evaluate EXP=R` twice,
identical scores) and red-team (`dev/bin/box make redteam EXP=R`, 0 holes). The prompt states only rules the evaluator enforces.

Approval: the scientist records `plan`.

## Run mode

1. Act: `/evolve R`: the search runs in the detached container `sc26-mxp-optimization` (refuses
   an unapproved plan); progress `dev/bin/box make status EXP=R`; `docker stop` ends it.
2. Verify: `dev/bin/box make harvest EXP=R`; for the top 3, the diff against seed.cpp and why the rewrite
   reduces rounding error while staying exact in real arithmetic; re-score the best.
3. Acceptance: the scientist records `candidate <id>`; `dev/bin/box make apply EXP=R ID=<id>`.

## Checks (the verification boundary)

- Every candidate: rules audited before the build, `make RAPTOR=1`, the bf16 run, the fp64
  equivalence guard; anything else changed outside the block scores null.
- Calibration and red-team before the search; re-score and `make check` before acceptance.

## Boundaries

- May write: R (except approvals.toml); app/ only through `make apply`.
- One search at a time: each evaluation swaps a candidate into app/.

## Provenance

R keeps plan.md, approvals.toml, experiment.yaml, evaluator.py, seed.cpp and results/
(fp64_reference.csv, baseline, redteam.md, evaluations.jsonl, checkpoints, candidates).
