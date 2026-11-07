# mxp-optimization

An agent system (Optimization thrust) for the Deforming Bubble mini-app in `app/` (WENO5 level
set, MPI C++). Start with `dev/README.md`.

Agents run natively; everything that builds or runs the app runs in the `hpc-lab-mxp` container
(clang 20, RAPTOR, MPI, OpenEvolve): `dev/bin/box make ...`. Never call make or a compiler directly.

- raptorize (interactive session, skill `.agents/skills/raptorize/SKILL.md`): RAPTOR precision
  modes, an FP64 shadow and an EVOLVE-BLOCK for `advectWeno`.
- optimize (OpenEvolve search, skill `.agents/skills/optimize/SKILL.md`): the kernel made more
  accurate under bf16.
- Entry points: `dev/bin/box`, `dev/bin/patch` (raptorize checkpoints), `dev/bin/evolve` (search).
- pi commands (shortcuts): /check /runs /approve /evolve /evolve-status /evolve-stop.
