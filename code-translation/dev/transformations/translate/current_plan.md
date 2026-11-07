# Plan: translate

Planned with: pi using hpc-lab/agent, 2026-11-07

## Each author session (one iteration of `dev/bin/loop`)

1. Read `agent_log.md` and `approvals.toml`; the harness gives you the open review items.
   The current group is the first with a unit not `verified`. If the group before it is not
   approved, change nothing and report `STATUS: COMPLETE` with "Group <k> awaits approval".
2. Fix what the review reports first. Otherwise take the next unit of the current group that
   `readiness` shows as ready (earlier units of the group make later ones ready).
3. Settle that one unit:
   a. read it, its callers (`grep -n <name> app/src/*`) and the Spec's rules and traps;
   b. write the C++ (and shim), `rm app/src/<unit>`;
   c. `oracle`. PASS: log `verified`. FAIL: fix and rerun; if you cannot, restore the unit
      (`git checkout -- app/src/<unit>`, `rm` the new files) and log `failed`.
4. Report `STATUS: COMPLETE` if every unit of the group is now `verified` ("Group <k> ready for
   approval"), else `STATUS: INCOMPLETE` with the next unit. One unit per session.

## Log

Append one line per unit to `agent_log.md`:

    - <unit> | <group> | <status> | <oracle's last line> | <files added/removed>

## Groups

- Group 1: kinds.F90 (header + shim), boundary.F90, config.F90 (+ shim), laplacian.F90
- Group 2: reaction.F90, stats.F90, grid.F90 (+ shim), output.F90
- Group 3: timestep.F90, initial.F90, integrator.F90
- Group 4: driver.F90, main.F90 (delete the shims)
