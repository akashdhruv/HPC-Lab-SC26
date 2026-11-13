# Plan: app-translate

Planned with: pi using hpc-lab/agent, 2026-11-07

## Each author session (one iteration of `dev/bin/loop`)

1. Read `agent_log.md` and `approvals.toml`; the harness gives you the open review items.
   The current group is the first with a unit not `verified`. Groups 1–3 are one continuous
   translation batch: do not wait for approval between them. Group 4 may begin only after the
   scientist has approved `Groups 1-3`; without that approval, change nothing and report
   `STATUS: INCOMPLETE` with "Groups 1-3 await approval" in NEXT STEPS (this is a blocker, not
   completion).
2. Fix what the review reports first. Otherwise take the next unit of the current group that
   `readiness` shows as ready (earlier units of the group make later ones ready).
3. Settle that one unit:
   a. read it, its callers (`grep -n <name> app/src/*`) and the Spec's rules and traps;
   b. write the C++ (and shim if a module is still used by Fortran);
   c. `rm app/src/<unit>.F90` (mandatory: a leftover original next to its shim defines the same
      module twice and breaks the build);
   d. if any C/C++ entry point is still called from Fortran, declare it `extern "C"` under the
      mangled name `<name>_` with pointer args and a trailing `size_t` length per character arg;
   e. `oracle`. PASS: log `verified`. FAIL: fix and rerun; if you cannot, restore the unit
      (`git checkout -- app/src/<unit>.F90`, `rm` the new files) and log `failed`.
4. After settling a unit, report `STATUS: INCOMPLETE` with the next unit while any unit in the
   current scope (Groups 1–3 before approval; Group 4 after) remains unverified, including at
   the boundaries after Groups 1 and 2. A review fix for one unit does not make the group
   complete. Report `STATUS: COMPLETE` only when every unit in the current scope is `verified`
   ("Groups 1-3 ready for approval" / "Group 4 ready"). Never report COMPLETE for a single
   settled unit. One unit per session.

## Log

Append one line per unit to `agent_log.md`:

    - <unit> | <group> | <status> | <oracle's last line> | <files added/removed>

## Groups

- Group 1: kinds.F90 (header + shim), boundary.F90, config.F90 (+ shim), laplacian.F90
- Group 2: reaction.F90, stats.F90, grid.F90 (+ shim), output.F90
- Group 3: timestep.F90, initial.F90, integrator.F90
- Group 4: driver.F90, main.F90 (delete the shims)
