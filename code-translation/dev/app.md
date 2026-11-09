# Application interface

An application can use this system if it has:

1. Fortran in `app/src/*.F90`, one unit (program, module or external procedures) per file,
   built by `app/Makefile` with gfortran and g++ into one executable. The Makefile discovers
   `src/*.F90` and `src/*.cpp` (Fortran in the order of `dev/tools/index.py order`), so a unit
   can be swapped for C++ without touching it.
2. A run in seconds, from `app/`, with no arguments beyond its input file, whose output
   contains lines a script can compare (here `diag` lines of numbers).
3. A golden output of the original Fortran (`app/tests/golden.out`) and a comparison with a
   tolerance (`app/tests/compare.py`), wrapped as the oracle `app/tests/check.sh`: clean build, one
   run, compare; exit 0 means correct.
4. Deterministic output: two runs of the same build give the same numbers.
