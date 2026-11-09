# code-translation/dev: class Translation(Lab)

A level of the tools (`../../tools/README.md`): Fortran -> C++ with its own loop.
`image = "hpc-lab-translate"`.

| tool | |
|---|---|
| `oracle` | clean build, one run, compare with `app/tests/golden.out` (exit 0: correct) |
| `check` (no stub) | override: the oracle, run by `../tools/setup` |
| `readiness [--json]` | which Fortran units can be translated now (`tools/index.py`) |
| `build [args]` | `make -C app` |
| `loop [-f\|--stop] <name> [loops]` | the loop (`tools/loop.py`) on a transformation, detached |
| `status [name]` | approvals, groups, agent log and the loop of a transformation |

Inherited from Lab, through `../tools/`: `approve`, `container`, `setup`.

- `app.md`: the interface an application must meet.
- `tools/loop.py`: this system's harness, the author -> oracle -> reviewer loop on CodeScribe.
- `tools/index.py`: the unit index (readiness, build order), run in the container.

Instances, outside dev/: `../transformations/<T>/` (spec, plan, loop.toml, approvals.toml, runs/),
here `app-translate`.
