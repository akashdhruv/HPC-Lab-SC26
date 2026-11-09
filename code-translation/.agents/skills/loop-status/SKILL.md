---
name: loop-status
description: Approvals, groups, agent log and loop runs of a transformation (dev/bin/status [name]); when the loop has stopped, verify the group and recommend acceptance.
---

Run `dev/bin/status [name]` from `code-translation/` and summarise it in a few lines: what is
approved, what the loop is doing or why it stopped.

If the loop has stopped at the end of a group, verify it; run the tools, never guess:

1. `dev/bin/oracle` must pass; also run `dev/bin/readiness` and `git status --short app/`.
2. Every `verified` line in `agent_log.md` must be a unit now in C++ with its `.F90` gone.
3. Spot-check one unit against the rules and traps in `desired_spec.md`; quote the lines.
4. Show a table unit | status | evidence | your check, then recommend "accept Group <k>" or what
   to fix. The scientist accepts with `../tools/approve transformations/<name> "Group <k>"`;
   never run it yourself.
