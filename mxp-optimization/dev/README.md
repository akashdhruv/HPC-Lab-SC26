# mxp-optimization: an agent system for mixed precision (Optimization thrust)

Two stages, each a contract any orchestrator can run (one skill file per stage):

| stage | pattern | why |
|---|---|---|
| `../.agents/skills/raptorize/` | interactive session | one careful change to the kernel, with decisions at three checkpoints |
| `../.agents/skills/optimize/` | evolutionary search (OpenEvolve) | open-ended objective, trustworthy score, many candidates |

- `app.md`: the interface an application must meet.
- `workflows/raptorize/`: the worked example (`kernel.cpp`) and `reference.patch`;
  `workflows/optimize/`: the harness (`run.py`, the evaluator).
- `tools/RAPTOR`, `tools/OpenEvolve`: submodules, built into the `hpc-lab-mxp` image (Dockerfile);
  `tools/search.sh` is the search inside a detached container.
- `bin/box` runs a command in the image, `bin/evolve` starts an approved search,
  `bin/patch` saves app's state at a checkpoint.
- `../experiments/<E>/<n>-<stage>/`: one instance per run, its provenance record.

Each stage: plan mode -> approval -> run mode -> acceptance.
