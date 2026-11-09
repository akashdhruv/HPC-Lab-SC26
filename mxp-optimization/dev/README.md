# mxp-optimization/dev: class Mxp(Lab)

A level of the tools (`../../tools/README.md`): mixed precision for the Deforming Bubble.
`image = "hpc-lab-mxp"`.

| tool | |
|---|---|
| `check` (no stub) | override: the app's tests, `make check`, run by `../tools/setup` |
| `new raptorize\|optimize <E>` | the next instance R, `experiments/<E>/<n>-<stage>`, from the skill's templates |
| `patch <R>/patches/<k>-<name>.patch` | app's state at a raptorize checkpoint |
| `evolve [--status\|--stop\|--resume] <R>` | an approved search in the detached container `hpc-lab-mxp-optimization` |
| `animate <R> [id]` | a candidate against the seed: `<R>/results/animation.mp4` |

Inherited from Lab, through `../tools/`: `container` (`../tools/container make ...`),
`approve`, `setup`.

- `app.md`: the interface an application must meet.
- `tools/RAPTOR`, `tools/OpenEvolve`: submodules built into the image; `tools/search.sh`: the
  search inside the detached container.

Two stages, each a skill (`../.agents/skills/<stage>/`: SKILL.md, templates/, examples/ or scripts/):

| stage | pattern | why |
|---|---|---|
| raptorize | interactive session | one careful change to the kernel, decisions at three checkpoints |
| optimize | evolutionary search (OpenEvolve) | open-ended objective, trustworthy score, many candidates |

Instances: `../experiments/<E>/<n>-<stage>/`, each its own provenance record. Each stage:
plan mode -> approval -> run mode -> acceptance.
