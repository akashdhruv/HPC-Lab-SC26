# code-translation

An agent system (Translation thrust): Fortran -> C++ for `app/`, rd2d, a Gray-Scott
reaction-diffusion mini-app of 13 Fortran units. Stage: translate (skill `translate`).

Agents run natively; everything that builds or runs the app runs in the `sc26-translate`
container through `dev/bin/`: `oracle` (tests/check.sh), `readiness` (dev/tools/index.py),
`build` (make -C app), `box <command>`. Never call make, gfortran or g++ directly.

- `app/`: `src/*.F90` and `src/*.cpp` (discovered by the Makefile), `include/FArray.hpp`, `input.nml`.
- `dev/tools/`: `pi-loop.sh`, `codescribe-loop.sh`, `status.sh`, `index.py`.
- `dev/transformations/<name>/`: one folder per transformation.
- pi commands: /readiness /check /approve /loop /codescribe /status.
