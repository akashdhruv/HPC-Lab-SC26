# Tools

Every tool of the tutorial is a public method of a class, called through a stub file. The classes
follow the directory tree and inherit along it: the root's `Lab` is the base class, each agent
system a subclass. The root holds only setup and what every system inherits; everything a system
does is in its own `dev/`. This file is the contract; `hpclab.py` implements it.

```
SC26-Tutorial/tools/        Lab                 setup approve container            (check)
code-translation/dev/       Translation(Lab)    oracle readiness build loop status   check
mxp-optimization/dev/       Mxp(Lab)            new evolve patch animate             check
```

## Levels

A **level** is the root or a system. The root's class is `Lab` in `tools/hpclab.py`, its stubs are
in `tools/`; a system is a directory with `dev/tools.py`. A level's parent is the nearest level
above it.

```
tools/                      the root
  setup approve container   stubs
  hpclab.py                 class Lab; Level and dispatch; Venv, Job, Config, Approvals, Container
  requirements.txt          .venv
  README.md                 this contract

<system>/dev/
  tools.py                  the system's class, the only Level subclass in the file:
                              class Translation(parent(__file__)): ...
  bin/<tool>                a stub per tool the system adds or overrides
  tools/                    what its tools use: its harness (each system writes its own, e.g.
                            code-translation's loop.py), modules, in-container scripts, submodules
  README.md                 its tools and what else lives in its dev/
  app.md                    the interface an application must meet
```

`dev/` holds tools only. A system's instances are its siblings:

- `transformations/<T>/`: **procedures**, specified and approved before they run (spec, plan,
  loop.toml), with an exact check, and rerunnable; `<T>` names what it transforms
  (`app-translate`). Their per-run state (approvals, agent log, `runs/`) lives with them.
- `experiments/<E>/<n>-<stage>/`: **records** of open-ended work, whose outcome is found during
  the run through scientist decisions or search.

## Tools

1. A tool is a public method of a level class; `Level` (the machinery) defines none. Helpers are
   properties, `_`-prefixed, or classes and functions outside the level class. A public method
   without a stub is still inherited and overridable, but only code calls it (`check`, by `setup`).
2. Arguments are strings, positional; a tool returns an exit code (`None` is 0). Its usage comes
   from its signature (`<required> [optional] [rest ...]`); a tool that parses its own flags opens
   its docstring with the synopsis instead: `"[-f|--stop] <name> [loops]: ..."`.
   `<stub> --help` prints the usage and docstring.

## Stubs and dispatch

3. A stub is a declaration, not code: every stub is the same file (a sh/python polyglot that
   finds the root and calls `hpclab.main(__file__)`), named after its tool; only its two comment
   lines (what it does, which method it runs) differ. A level carries stubs only for the tools
   it **adds or overrides**; inherited tools are reached through the root's stub.
4. A stub runs its tool on the **deepest level between the stub's level and the working
   directory**: `../tools/container make check` from `mxp-optimization/` runs `Mxp.container`
   (inherited from `Lab`) in `Mxp.image`. Called from outside its level, a stub runs on its own level.
5. A system declares state as class attributes (`image = "hpc-lab-mxp"`); the inherited tools use
   it (`self.docker`). `Lab` iterates the systems (`self.children`, `self.walk()`): `setup` builds
   every image and runs every system's `check`. The root never names a system.

## Orchestrators

6. Agents call tools by path (`dev/bin/oracle`, `../tools/container`). With
   `orchestrator.dev_bin_on_path: true` in `config.yaml`, Claude Code and pi also put the system's
   `dev/bin`, then `tools/`, on PATH, so a bare `container` resolves as rule 4 does. `approve`
   stays the scientist's: the adapters block it.
   With `claude.enabled: true` in `config.yaml`, `tools/setup` writes Claude Code's endpoint
   (`ANTHROPIC_BASE_URL`, model names, `apiKeyHelper`) to each `.claude/settings.local.json`
   (its `env`, `model` and `apiKeyHelper` keys; others stay). Rerun setup after editing.

## Portability

7. Pure Python >= 3.8, stdlib only (PyYAML for `config.yaml`, from `.venv`): every tool behaves
   the same on Windows, macOS and Linux. A tool that needs `.venv` calls `Venv().activate()`.
   Anything that builds or runs an app runs in the system's image, never on the host.
8. Stubs are sh/python polyglots, run by bash/zsh and, on Windows, Git Bash; from cmd.exe or
   PowerShell call them through Python (`python tools/setup`). No `.cmd` twins are tracked: a
   harness whose commands go through cmd.exe writes its own shims (code-translation's loop puts
   `<tool>.cmd` for its `dev/bin` in `runs/bin/` on Windows, `loop.shims`).

## Adding

- A tool to a system: a method on its class, then a stub in its `dev/bin/` (copy any stub).
- An override: the method only; the root's stub already reaches it.
- A shared tool: a method on `Lab` and a stub in `tools/`; every system inherits it.
- A system: a folder with `AGENTS.md`, `.agents/skills/`, a `Dockerfile`, `dev/tools.py`
  (`class X(parent(__file__))` with an `image` and a `check`), `dev/README.md`, `dev/app.md` and
  stubs for its tools. `tools/setup` builds and checks it with the others.
- A dedicated agent system of its own: seed a new repo from this one, the root (`tools/`,
  `config.yaml`, `.agents/adapters/`, `AGENTS.md`) and the system folders you keep.

## Root tools (Lab)

| tool | |
|---|---|
| `setup [--native]` | links for Claude Code and pi, `.venv`, pi; then submodules, images and checks of every system |
| `approve <instance> "<item>" [note]` | records an approval in `<instance>/approvals.toml`: the scientist only |
| `container [-d] <command ...>` | a command in the system's image, the tutorial at `/work`, the system as workdir |
| `check` (no stub) | the system's check, run by `setup`; each system overrides it |
