# HPC agent systems

Each folder is an agent system: the program of one HPC process (stage contracts, templates,
tools, provenance), independent of the orchestrator that runs it (pi, Claude Code, Codex,
OpenCode, ...). Start with `<system>/AGENTS.md`.

Every stage runs the same way, led by the scientist:

    plan mode  ->  approval  ->  run mode (act, verify)  ->  acceptance
    agent          scientist     harness, agent              scientist

Each stage uses the agent pattern that fits it: an interactive session (raptorize), an
autonomous loop (translate) or an evolutionary search (optimize).

## Where things are

- Stage contracts: one skill per stage, `<system>/.agents/skills/<stage>/SKILL.md`, with its
  `templates/`. Everything an orchestrator needs is in `AGENTS.md` and `.agents/`: Codex and
  OpenCode read them as they are; Claude Code and pi read their own `.claude/`, `.pi/`, which
  `tools/setup` makes as untracked links into `.agents/` (`.agents/adapters/`). If your orchestrator lists no such skill, read that SKILL.md yourself when the
  scientist asks for the stage.
- Entry points: `tools/*` and `<system>/dev/bin/*`, plain Python. Call them by path
  (`dev/bin/oracle`); the same name works in bash, Git Bash, cmd.exe and PowerShell (a `.cmd`
  twin). Builds and runs happen in each system's docker image; agents and model calls run natively.
- Shortcuts: `!<shell line>` runs a line in any orchestrator; the systems' skills are the rest.
- Model endpoint of the harnesses (the loop `tools/loop.py`, OpenEvolve): `config.yaml`.
- Setup: `tools/setup` (`--native` skips docker); python packages only in `.venv`
  (`hpclab.Venv`: made on first use, first on PATH in pi and Claude Code sessions).

## Rules

- Follow the stage contract; run the tools, never guess correctness.
- A stage's "plan mode" writes the plan files for approval; it is not your orchestrator's own
  read-only plan mode.
- Never write approvals.toml or run `tools/approve`: only the scientist does.
- Never print the key in config.yaml; never stage or commit.
