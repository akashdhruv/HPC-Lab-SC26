---
name: raptorize
description: Run the raptorize stage in an interactive session: add RAPTOR precision modes, an FP64 shadow, error columns and an EVOLVE-BLOCK to one kernel of app/, with the scientist deciding at three checkpoints. Use when the user wants to raptorize, add precision modes, or prepare a kernel for optimization.
---

# raptorize (interactive session)

The stage contract. Role: make one kernel of `app/` runnable at emulated precisions without
changing what the app does at fp64: precision modes through RAPTOR, an FP64 shadow run, error
columns, and the EVOLVE-BLOCK that optimize will evolve. A judgment-heavy, one-off change, so it
is done with the scientist at three checkpoints, not by a loop. Instance R:
`experiments/<E>/<n>-raptorize/`. Commands run from `mxp-optimization/`; builds and runs happen
in the container (`dev/bin/box`). Worked example: `dev/workflows/raptorize/kernel.cpp`; a
finished raptorize for comparison: `dev/workflows/raptorize/reference.patch`.

## Plan mode

1. Check: `git status app` is clean; `dev/bin/box make check` passes.
2. `dev/bin/box make run STAGE=raptorize E=<yyyy-mm-dd>` prints R.
3. Read `app/src/advect.cpp` and its callers; ask (proposing a default for each, explained
   plainly) and write R/plan.md, including who planned it (your orchestrator and model):

| question | default |
|---|---|
| kernel | `advectWeno` in `src/advect.cpp`, object `build/advect.o` |
| formats (exponent, mantissa) | fp32 (8, 23), bf16 (8, 7) |
| seed | none: the EVOLVE-BLOCK is the FP64 kernel itself, truncated by RAPTOR |
| evolve scope | `wenoFaceValue` and `advectWeno`: all code truncated in the target mode |
| errors | `err_rms`, `err_max` of phi vs the shadow, appended to `history.csv` |
| eval run | `mpirun -n 1 ./bubble params/bubble.ini nx=128 ny=128 max_steps=100 plot_interval=0 precision={mode} outdir={out}` |

4. The scientist approves with `../tools/approve <R> plan`.

## Run mode, with checkpoints

Stop at each checkpoint, show the evidence, and wait for the scientist:

1. Scope: the files to touch and the planned blocks; `dev/bin/patch <R>/patches/1-scope.patch`.
2. Diff: follow `kernel.cpp`; self-check `git diff -U0 app` (every removed line has a
   `RAPTOR: was` twin); `dev/bin/patch <R>/patches/2-diff.patch`.
3. Results: `dev/bin/box make clean`, `dev/bin/box make check`, `dev/bin/box make RAPTOR=0 check`,
   then the eval run per mode into `<R>/results/<mode>`; a table of the final error per mode;
   `dev/bin/patch <R>/patches/3-results.patch`.

Acceptance: the scientist records `../tools/approve <R> result`; optimize can start.

## Code rules

- Only add code; never rename, move, reorder or reformat existing code.
- New code in `// RAPTOR-BEGIN: <purpose>` ... `// RAPTOR-END` blocks (`#` in Makefiles); an
  added line ends with `// RAPTOR`, a changed line with `// RAPTOR: was <old line>`.
- `__raptor_truncate_op_func(fn, 64, 1, E, M)` truncates fn and its callees in the same file;
  RAPTOR code sits under `#ifdef BUBBLE_RAPTOR`, so `make RAPTOR=0` still builds fp64.
- The shadow is a separate fp64 run: its own state, copied once, advanced by the unchanged step
  with the main run's dt.
- The build change goes in app/Makefile using the RAPTOR* variables of the root Makefile.
- Keep a use of `sqr` outside the block, or `-Werror` fails on an unused function.

## Checks (the verification boundary)

- fp64 output unchanged (`history.csv` of `precision=fp64` equals the original run).
- Every other mode has a finite, nonzero error.
- Floor check: truncate only the code outside the block; if that error is close to the full
  target error, widen the block.

## Boundaries

- May write: app/'s sources and Makefile, R. Must not: app/tests, the root Makefile.
- Never write `approvals.toml` or run `tools/approve`.

## Provenance

R keeps plan.md (decisions, checkpoint outcomes), approvals.toml, patches/ (app's state at each
checkpoint) and results/ (the eval run per mode).
