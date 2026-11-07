---
name: raptorize
description: Run the raptorize stage in an interactive session: add RAPTOR precision modes, an FP64 shadow, error columns and an EVOLVE-BLOCK to one kernel of app/, with the scientist deciding at three checkpoints. Use when the user wants to raptorize, add precision modes, or prepare a kernel for optimization.
---

# raptorize (interactive)

Read `dev/workflows/raptorize/system.md` (the contract) and `kernel.cpp` (the worked example).
This stage is a careful one-off change, so it is done with the scientist, not by a loop.
Builds and runs happen in the container: prefix them with `dev/bin/box`.

## Plan mode

1. Check: `git status app` is clean; `dev/bin/box make check` passes.
2. `dev/bin/box make run STAGE=raptorize E=<yyyy-mm-dd>` prints R.
3. Read `app/src/advect.cpp` and its callers; ask the contract's questions with defaults,
   explaining each plainly; write R/plan.md.
4. Ask for approval: `/approve <R> plan`.

## Run mode

Stop at each checkpoint, show the evidence, and wait for the scientist:

1. scope: files and blocks; `dev/tools/patch.sh <R>/patches/1-scope.patch`.
2. diff: the edits, following `kernel.cpp`; the self-check; `dev/tools/patch.sh <R>/patches/2-diff.patch`.
3. results: `dev/bin/box make clean`, `dev/bin/box make check`, `dev/bin/box make RAPTOR=0 check`,
   the eval run per mode into `<R>/results/<mode>`, a table of errors;
   `dev/tools/patch.sh <R>/patches/3-results.patch`.

The scientist accepts with `/approve <R> result`; then the optimize stage starts.
`dev/workflows/raptorize/reference.patch` is a finished raptorize for comparison.

Never write approvals.toml.
