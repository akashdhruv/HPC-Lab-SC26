# Spec: translate

Translate all 13 Fortran units in `app/src` to C++ while preserving the application's numerical behavior.

## Contract

- Objective: every unit in scope is replaced by C++ and logged `verified`.
- Invariants, after every unit: `build` succeeds; `oracle` passes; the remaining Fortran
  still links; `tests/` and `app/Makefile` are unchanged.
- Oracle: `oracle` (tests/check.sh in the container): clean build, one run, every `diag` number within rtol
  1e-12 of the original Fortran's output. Run it; never infer it.

| status | meaning | evidence |
|---|---|---|
| verified | translated, oracle passes | oracle's PASS line |
| failed | could not pass; unit restored to Fortran | oracle's FAIL lines |
| blocked | needs a human | the reason |

## Scope

`kinds.F90 boundary.F90 config.F90 laplacian.F90 reaction.F90 stats.F90 grid.F90 output.F90 timestep.F90 initial.F90 integrator.F90 driver.F90 main.F90`

## Units and readiness

A unit is one `app/src/<name>.F90` (not a `*_fi.F90` shim). It is ready when `readiness` shows
`yes`: everything it uses or calls is already C++.

## Translation rules

1. Replace `<name>.F90` with `<name>.cpp` (+ `.hpp` if C++ calls it); delete the `.F90`.
2. External procedures still called from Fortran: `extern "C"`, gfortran's name (lower case +
   `_`), every argument by pointer; `double` for `real(rk)`, `int` for `integer`, `int64_t` for
   `integer(ik)`. A character argument adds a hidden trailing `size_t` length.
3. Modules still used by Fortran keep a shim `<name>_fi.F90`: the same module name and public
   interface, implemented with `bind(C)` interfaces, interoperable types (`bind(C)` derived
   types mirrored by C++ structs) and `c_f_pointer` for module data. A parameter-only module
   (`kinds`) becomes a header plus a shim that repeats the parameters. Delete a shim when its
   last Fortran user is gone.
4. Arrays: wrap pointers in `FArray2D<double>` (`include/FArray.hpp`) with the Fortran bounds
   (`0:nx+1` -> lower bound 0), so `f(i, j)` reads the same.
5. Array syntax, elemental calls and `where` become loops over the same index range, `j` outer
   and `i` inner; each Fortran statement finishes before the next starts.
6. `main.F90` becomes `int main()` in `main.cpp`, reading the same `input.nml`.
7. Keep operation order and literal precision.

## Silent traps

- `real :: r` and `real(state)/2147483648.0` are single precision (`float`).
- The LCG must visit cells in the same order (`j` outer, `i` inner) as the Fortran.
- `maxloc(v(1:nx,1:ny))` returns the first maximum in column-major order, 1-based.
- `where (g%v < 0) ...` covers guard cells too; `count(mask)` and `sum` are column-major.
- `select case (trim(bc_y))`: compare the trimmed string, length from the hidden argument.
- Namelist input: `key = value` pairs, `d0` exponents, quoted strings, commas, ends at `/`.
- `nx /= ny`: swapped indices fail the oracle.
