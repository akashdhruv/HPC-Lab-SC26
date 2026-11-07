# SC26 hands-on: programmable agent systems for scientific software

An agent system is the program of an HPC process, written as version-controlled files: stage
contracts, templates, tools and a provenance record. It runs under any orchestrator (pi,
Claude Code, Codex, OpenCode, ...) on Windows, macOS or Linux. Every stage runs the same way:

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
| `code-translation/` | translate (CodeScribe loop) | `tests/check.sh`: the original Fortran's output to 1e-12 |
| `mxp-optimization/` | raptorize (session), optimize (OpenEvolve) | fp64 unchanged; an audited, red-teamed evaluator with an equivalence guard |

## What runs where

- **Orchestrator** (yours): the interactive stages and plan modes. It reads `AGENTS.md`
  and the skills in `<system>/.agents/skills/`. Only `AGENTS.md` and `.agents/` are tracked:
  Codex and OpenCode read them directly, and `tools/setup` links Claude Code's `.claude/` and pi's
  `.pi/` into `.agents/` (symlinks; on Windows junctions, or copies where symlinks are refused).
- **Harnesses** (the system's): the translate loop (`tools/loop.py` on the CodeScribe library,
  started by `dev/bin/loop`) and the optimize search (OpenEvolve, `dev/bin/evolve`). They call the model in `config.yaml` and enforce their
  own rules, so they behave the same whichever orchestrator, or person, starts them.
- **Containers**: every build, run and search, one docker image per system.

## Setup

Native: git, Docker, Python >= 3.10 and an orchestrator (any of them); Node.js if that is
[pi](https://pi.dev). On Windows, Git for Windows (its Git Bash runs `setup.sh`; its tools serve
the loop).

```bash
git clone --recursive <this repo> && cd SC26-Tutorial
tools/setup                      # .venv (CodeScribe from git), images, both checks; --native skips docker
$EDITOR config.yaml              # endpoint and key of the harnesses (and of pi)
cd code-translation && pi        # or claude, codex, opencode; or cd mxp-optimization
```

Every entry point (`tools/*`, `<system>/dev/bin/*`) is Python and is called by path, the same in
bash, Git Bash, cmd.exe and PowerShell (`./setup.sh` is the same as `tools/setup`). Python
packages go only into the tutorial's `.venv`: `tools/requirements.txt` pins CodeScribe to a commit
of its git repo; entry points that need it make `.venv` on first use and rerun under it, and
pi and Claude Code sessions put it first on PATH.

## The translate loop, from any orchestrator

    orchestrator (pi, claude, codex, opencode)  ->  dev/bin/loop -b <name>  ->  .venv python
        ->  tools/loop.py (author -> check -> review)  ->  codescribe.lib (Agent, tools, telemetry)

`tools/loop.py` is the lab's own loop, tracked here: the policy of `loop.toml` (protected files,
bash allowlist, reviewer rules), the oracle after every author session and the stop rule are this
repo's code; CodeScribe supplies the agent, its bounded tools and the model client. Each run is
recorded in `dev/transformations/<name>/runs/<run_id>/`. The orchestrator only launches it:
the `csloop` skill, the translate skill's run mode, or the shell line itself.

## A stage, in any orchestrator

Ask for the stage ("translate, plan mode"); the agent follows the skill. The scientist's and
the harness's steps are shell lines (from the system folder):

| | translate | raptorize | optimize |
|---|---|---|---|
| plan mode | skill `translate` | skill `raptorize` | skill `optimize` |
| approval | `../tools/approve dev/transformations/<name> plan` | `../tools/approve <R> plan` | `../tools/approve <R> plan` |
| run mode | `dev/bin/loop -b <name>`, `dev/bin/status <name>` | the skill, 3 checkpoints | `dev/bin/evolve <R>`, `dev/bin/container make status EXP=<R>` |
| verify | the skill's run mode | the checkpoint 3 table | the skill's run mode |
| acceptance | `../tools/approve dev/transformations/<name> "Group 1"` | `../tools/approve <R> result` | `../tools/approve <R> "candidate <id>"` |

In any orchestrator, `!` + a line runs it (`!../tools/approve dev/transformations/<name> plan`);
skills run the stages (`/skill:translate` in pi), plus `csloop` and `csloop-status` in
code-translation. Approvals go only through `tools/approve`, run by the scientist; act steps
refuse unapproved plans. pi (`.agents/adapters/pi/hpclab/guard.ts`) and Claude Code
(`.agents/adapters/claude/settings.json`) also block the agent from approving.

## Layout

```
config.yaml                            endpoint of the harnesses (and of pi)
tools/                                 setup, approve, approved, container; hpclab.py (shared helpers)
tools/loop.py, tools/requirements.txt  the translate loop; the pinned .venv packages (CodeScribe)
.agents/adapters/                     Claude Code's settings, pi's settings and extension (hpclab:
                                       provider, compact output, approvals guard), linked by setup

code-translation/
  .agents/skills/translate/            the stage: SKILL.md + templates/
  app/, tests/check.sh, dev/app.md     rd2d (13 Fortran units), its oracle, the app interface
  dev/bin/                             oracle, readiness, build, container, loop, status
  dev/transformations/<name>/          one folder per transformation; runs/ holds each loop's record

mxp-optimization/
  .agents/skills/{raptorize,optimize}/ the stages: SKILL.md + templates/
  app/, dev/app.md                     the bubble mini-app (untouched FP64 code), the app interface
  dev/bin/                             container, evolve, patch
  dev/workflows/                       worked example and reference.patch; the search harness
  dev/tools/RAPTOR, dev/tools/OpenEvolve   submodules
  experiments/<E>/<n>-<stage>/         one folder per stage run
```
