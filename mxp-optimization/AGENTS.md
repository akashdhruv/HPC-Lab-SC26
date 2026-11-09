# mxp-optimization

An agent system (Optimization thrust) for the Deforming Bubble mini-app in `app/` (WENO5 level
set, MPI C++). Its tools: `dev/README.md` (class `Mxp(Lab)` in `dev/tools.py`); the interface an
application must meet: `dev/app.md`.

Agents run natively; everything that builds or runs the app runs in the `hpc-lab-mxp` container
(clang 20, RAPTOR, MPI, OpenEvolve) through the inherited `../tools/container make ...`. Never
call make or a compiler directly.

Each stage is a skill and an instance, `experiments/<E>/<n>-<stage>/` (made by `dev/bin/new`),
its own provenance record:

    plan mode  ->  approve plan  ->  run mode  ->  accept (result / candidate <id>)
    agent          scientist         agent         scientist

- raptorize (interactive session, `.agents/skills/raptorize/SKILL.md`): RAPTOR precision modes,
  an FP64 shadow and an EVOLVE-BLOCK for `advectWeno`; checkpoints with `dev/bin/patch`.
- optimize (OpenEvolve search, `.agents/skills/optimize/SKILL.md`): the kernel made more accurate
  under bf16. `dev/bin/evolve <R>` runs this system's search (`dev/tools/search.sh`, models from
  config.yaml) detached, in the container `hpc-lab-mxp-optimization`; `--status`, `--stop`,
  `--resume`. `dev/bin/animate <R> [id]` renders a candidate against the seed.
- `../tools/approve <R> plan`, then `result` or `"candidate <id>"`: scientist only.
