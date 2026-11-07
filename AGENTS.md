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
  `templates/`. pi, Codex and OpenCode discover them; `.claude/skills` is a symlink to the same
  folder. If your orchestrator lists no such skill, read that SKILL.md yourself when the
  scientist asks for the stage.
- Entry points: `tools/*` and `<system>/dev/bin/*`, plain Python. Call them by path
  (`dev/bin/oracle`); the same name works in bash, Git Bash, cmd.exe and PowerShell (a `.cmd`
  twin). Builds and runs happen in each system's docker image; agents and model calls run natively.
- Model endpoint of the harnesses (CodeScribe loop, OpenEvolve): `config.yaml`.

## Rules

- Follow the stage contract; run the tools, never guess correctness.
- A stage's "plan mode" writes the plan files for approval; it is not your orchestrator's own
  read-only plan mode.
- Never write approvals.toml or run `tools/approve`: only the scientist does.
- Never print the key in config.yaml; never stage or commit.
