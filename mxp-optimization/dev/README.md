# mxp-optimization: an agent system for mixed precision (Optimization thrust)

Two stages, each a contract any orchestrator can run:

| stage | pattern | why |
|---|---|---|
| `workflows/raptorize/` | interactive session | one careful change to the kernel, with decisions at three checkpoints |
| `workflows/optimize/` | evolutionary search (OpenEvolve) | open-ended objective, trustworthy score, many candidates |

- `app.md`: the interface an application must meet.
- `tools/RAPTOR`, `tools/OpenEvolve`: submodules, built into the `sc26-mxp` image (Dockerfile);
  `bin/box` runs a command in it, `tools/search.sh` is the search inside a detached container,
  `tools/patch.sh` saves app's state at a checkpoint.
- `../experiments/<E>/<n>-<stage>/`: one instance per run, its provenance record.

Each stage: plan mode -> approval -> run mode -> acceptance.
