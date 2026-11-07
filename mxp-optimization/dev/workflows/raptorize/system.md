# Stage contract: raptorize (interactive session)

Role: make one kernel of `app/` runnable at emulated precisions without changing what the app
does at fp64: precision modes through RAPTOR, an FP64 shadow run, error columns, and the
EVOLVE-BLOCK that optimize will evolve. A judgment-heavy, one-off change, so it is done in an
interactive session with three checkpoints. Instance R: `experiments/<E>/<n>-raptorize/`.

## Plan mode

The agent reads the kernel, asks (proposing a default for each) and writes R/plan.md:

| question | default |
|---|---|
| kernel | `advectWeno` in `src/advect.cpp`, object `build/advect.o` |
| formats (exponent, mantissa) | fp32 (8, 23), bf16 (8, 7) |
| seed | none: the EVOLVE-BLOCK is the FP64 kernel itself, truncated by RAPTOR |
| evolve scope | `wenoFaceValue` and `advectWeno`: all code truncated in the target mode |
| errors | `err_rms`, `err_max` of phi vs the shadow, appended to `history.csv` |
| eval run | `mpirun -n 1 ./bubble params/bubble.ini nx=128 ny=128 max_steps=100 plot_interval=0 precision={mode} outdir={out}` |

Approval: the scientist records `plan`.

## Run mode, with checkpoints

1. Scope: the files to touch and the planned blocks; `dev/tools/patch.sh R/patches/1-scope.patch`.
2. Diff: follow `kernel.cpp` (the worked example); self-check `git diff -U0 app | grep '^-[^-]'`
   (every removed line has a `RAPTOR: was` twin); `dev/tools/patch.sh R/patches/2-diff.patch`.
3. Results: in the container (`dev/bin/box`): `make clean`, `make check`, `make RAPTOR=0 check`,
   then the eval run per mode into `R/results/<mode>`; a table of the final error per mode;
   `dev/tools/patch.sh R/patches/3-results.patch`.

Acceptance: the scientist records `result`; optimize can start.

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

- May write: app/'s sources and Makefile, R. Must not: app/tests, the root Makefile, approvals.

## Provenance

R keeps plan.md (decisions, checkpoint outcomes), approvals.toml, patches/ (app's state at each
checkpoint) and results/ (the eval run per mode).
