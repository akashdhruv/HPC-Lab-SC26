# mxp-optimization: an agent system for mixed precision (Optimization thrust)

Two stages, each a contract any orchestrator can run (one skill file per stage):

| stage | pattern | why |
|---|---|---|
| `../.agents/skills/raptorize/` | interactive session | one careful change to the kernel, with decisions at three checkpoints |
| `../.agents/skills/optimize/` | evolutionary search (OpenEvolve) | open-ended objective, trustworthy score, many candidates |

A skill folder holds everything its stage owns: `SKILL.md` (the contract), `templates/` (an
instance's files), and raptorize's `examples/` (worked example, reference.patch) or optimize's
`scripts/` (the search harness and the animation). `dev/` holds what the system shares:

- `app.md`: the interface an application must meet.
- `tools/RAPTOR`, `tools/OpenEvolve`: submodules, built into the `hpc-lab-mxp` image (Dockerfile);
  `tools/search.sh` is the search inside a detached container.
- `bin/new` makes a stage's instance R, `bin/container` runs a command in the image,
  `bin/evolve` starts an approved search,
  `bin/patch` saves app's state at a checkpoint, `bin/animate` shows a candidate against the
  seed (`<R>/results/animation.mp4`).
- `../experiments/<E>/<n>-<stage>/`: one instance per run, its provenance record.

Each stage: plan mode -> approval -> run mode -> acceptance.
