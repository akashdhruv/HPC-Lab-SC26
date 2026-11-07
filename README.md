# SC26 hands-on: programmable agent systems for scientific software

An agent system is the program of an HPC process, written as version-controlled files: stage
contracts, templates, tools and a provenance record. It runs under any orchestrator; here pi
(and CodeScribe). Every stage runs the same way:

    plan mode  ->  approval  ->  run mode (act, verify)  ->  acceptance
    agent          scientist     harness, agent              scientist

## Which agent pattern, when

| pattern | use it when | stage here |
|---|---|---|
| interactive session | one careful change; decisions only the scientist can make; checkpoints | **raptorize**: precision modes and a shadow run for one kernel |
| autonomous loop (author -> oracle -> reviewer) | many similar units; a cheap, exact oracle | **translate**: 13 Fortran units to C++, one per iteration |
| evolutionary search (OpenEvolve; AlphaEvolve at scale) | an open-ended objective with no known answer, but a trustworthy score | **optimize**: rewrites of a kernel for accuracy under RAPTOR's bf16 emulation |

| system | stages | verification boundary |
|---|---|---|
| `code-translation/` | translate (loop: pi or CodeScribe) | `tests/check.sh`: the original Fortran's output to 1e-12 |
| `mxp-optimization/` | raptorize (session), optimize (OpenEvolve) | fp64 unchanged; an audited, red-teamed evaluator with an equivalence guard |

## Setup (Windows, macOS, Linux)

Native: [pi](https://pi.dev) (Node.js), git (on Windows, Git for Windows: pi uses its Git Bash),
Docker, and Python >= 3.10 for CodeScribe. The agents and their model calls run natively; every
build, run and search runs in one docker image per system.

```bash
git clone --recursive <this repo> && cd SC26-Tutorial
./setup.sh                       # pi, images sc26-translate and sc26-mxp, CodeScribe, both checks
$EDITOR config.yaml              # your endpoint and key
cd code-translation && pi        # or mxp-optimization; trust the folder once
```

On Windows, run these in Git Bash.

## A stage in pi

| | translate | raptorize | optimize |
|---|---|---|---|
| plan mode | `/skill:translate plan` | `/skill:raptorize plan` | `/skill:optimize plan` |
| approval | `/approve <name> plan` | `/approve <R> plan` | `/approve <R> plan` |
| run mode | `/loop <name>`, `/status` | `/skill:raptorize run` (3 checkpoints) | `/evolve <R>`, `/evolve-status <R>` |
| verify | `/skill:translate run` | the checkpoint 3 table | `/skill:optimize run` |
| acceptance | `/approve <name> "Group 1"` | `/approve <R> result` | `/approve <R> "candidate <id>"` |

Each `/command` is one shell line (`<system>/.pi/extensions/*.ts`), shown with its output.
Approvals go only through `tools/approve.sh`; act steps refuse unapproved plans.

## Layout

```
config.yaml, tools/                    shared: endpoint, approvals
.pi/extensions/sc26/                   pi adapter: provider, compact output, command helper

code-translation/
  app/, tests/check.sh                 rd2d (13 Fortran units) and its oracle
  dev/tools/, dev/bin/                 readiness, the two loop runners, status
  dev/transformations/<name>/          one folder per transformation
  .pi/skills/translate/                the stage: SKILL.md + templates/

mxp-optimization/
  app/                                 the bubble mini-app, untouched FP64 code
  dev/workflows/raptorize/             contract, worked example, reference.patch
  dev/workflows/optimize/              contract, templates, Evaluator, Run
  dev/tools/RAPTOR, dev/tools/OpenEvolve   submodules
  experiments/<E>/<n>-<stage>/         one folder per stage run
```
