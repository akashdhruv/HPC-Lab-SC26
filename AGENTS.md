# HPC agent systems

Each folder is an agent system: the program of one HPC process. Start with `<system>/AGENTS.md`.

Every stage runs the same way, led by the scientist:

    plan mode  ->  approval  ->  run mode (act, verify)  ->  acceptance
    agent          scientist     harness, agent              scientist

## Where things are

- Stage contracts: `<system>/.agents/skills/<stage>/SKILL.md` and its `templates/`
  (code-translation checks in its transformation instead). If your orchestrator lists no such
  skill, read that SKILL.md when the scientist asks for the stage.
- Entry points: `tools/*`, `<system>/dev/bin/*`. Call them by path (`dev/bin/oracle`).
- Model endpoint of the harnesses (`tools/loop.py`, OpenEvolve): `config.yaml`.
- Python packages only in `.venv` (made by `tools/setup`).

## Rules

- Follow the stage contract; run the tools, never guess correctness.
- A stage's "plan mode" writes plan files for approval; it is not your orchestrator's
  read-only plan mode.
- Never write approvals.toml or run `tools/approve`: only the scientist does.
- Never print the key in config.yaml; never stage or commit.
