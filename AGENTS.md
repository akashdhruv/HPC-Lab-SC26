# HPC agent systems

Each folder is an agent system: the program of one HPC process. Start with `<system>/AGENTS.md`.

Every stage runs the same way, led by the scientist:

    plan mode  ->  approval  ->  run mode (act, verify)  ->  acceptance
    agent          scientist     harness, agent              scientist

## Where things are

- Stage contracts: `<system>/.agents/skills/<stage>/SKILL.md` and its `templates/`
  (code-translation checks in its transformation instead). If your orchestrator lists no such
  skill, read that SKILL.md when the scientist asks for the stage.
- Tools (`tools/README.md`): a system's own in its `dev/bin/` (`dev/bin/oracle`), the shared ones
  in the root's `tools/`, inherited by every system (`../tools/container` runs as the system you
  are in). Call them by path — the adapters also put them on PATH, so by name works too; `--help` on any.
- `dev/` holds a system's tools only; its instances are siblings of `dev/`: `transformations/<T>/`
  (approved, rerunnable procedures) and `experiments/<E>/<n>-<stage>/` (records of open-ended
  work), each with its own `approvals.toml`.
- Each system writes its own harness in its `dev/tools/` (code-translation's `loop.py`, mxp's
  OpenEvolve search); their model endpoint: `config.yaml`.
- Python packages only in `.venv` (made by `tools/setup`).

## Rules

- Follow the stage contract; run the tools, never guess correctness.
- A stage's "plan mode" writes plan files for approval; it is not your orchestrator's
  read-only plan mode.
- Never write approvals.toml or run `tools/approve`: only the scientist does.
- Never print the key in config.yaml; never stage or commit.
