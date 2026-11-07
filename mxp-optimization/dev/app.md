# Application interface

An application can use this system if it has:

1. C++ in `app/`, built by `app/Makefile` and tested by `make check` from this folder; the
   kernel's file compiles alone to its own object file, so raptorize can route it through the
   RAPTOR plugin (`RAPTOR_CXX`, `RAPTOR_CXXFLAGS`, `RAPTOR_LDLIBS` from the root Makefile).
2. A kernel that is a free function on FP64 arrays, its FP callees in the same file.
3. A run command with key=value options (output directory, step cap, grid), a small case in
   seconds, writing a CSV with one row per step.
4. A copyable state and a step that takes dt from the loop, so a shadow run can be added.
5. Bitwise-identical output for two identical fp64 runs.
