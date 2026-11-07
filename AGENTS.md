# SC26 agent systems

Each folder is an agent system: the program of one HPC process (stage contracts, templates,
tools, provenance), independent of the orchestrator that runs it. Start with `<system>/AGENTS.md`.

Every stage runs the same way, led by the scientist:

    plan mode  ->  approval  ->  run mode (act, verify)  ->  acceptance
    agent          scientist     harness, agent              scientist

Each stage uses the agent pattern that fits it: an interactive session (raptorize), an
autonomous loop (translate) or an evolutionary search (optimize).

Rules: follow the stage contract (`system.md`, or the skill for translate); run the tools, never guess correctness; never write
approvals.toml (only `tools/approve.sh`, by the scientist); never print the key in config.yaml;
never stage or commit.
