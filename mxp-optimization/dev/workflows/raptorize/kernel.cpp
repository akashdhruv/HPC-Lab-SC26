// Worked example: what raptorize adds for a kernel Diffuse, with an FP callee Laplacian.
// Copy the shape, not the names; "..." is existing code of app/. Decisions in R/plan.md used:
// function Diffuse in diffuse.cpp, formats fp32 (8, 23) and bf16 (8, 7), lowprec float.

// ---- diffuse.h ----
// RAPTOR-BEGIN: precision modes of Diffuse
enum class Precision { kFp64, kFp32, kBf16, kLowPrec };
void DiffuseAt(Precision m, double nu, double dt, const double* u, double* out, int n);
// RAPTOR-END

// ---- diffuse.cpp ----
#include <stdexcept>  // RAPTOR

double Laplacian(const double* u, int i, int n) { ... }
void Diffuse(double nu, double dt, const double* u, double* out, int n) { ... }

// RAPTOR-BEGIN: Diffuse at precision m; optimize evolves the lowprec seed.
// EVOLVE-BLOCK-START
// The seed: Diffuse and its FP callees, copied in float and renamed *LowPrec.
float LaplacianLowPrec(const float* u, int i, int n) { ... }
void DiffuseLowPrec(float nu, float dt, const float* u, float* out, int n) { ... }
// EVOLVE-BLOCK-END

void DiffuseAt(Precision m, double nu, double dt, const double* u, double* out, int n) {
    if (m == Precision::kFp64) {
        Diffuse(nu, dt, u, out, n);
    } else if (m == Precision::kLowPrec) {
        // fp64 -> float, run the seed, float -> fp64.
        std::vector<float> uf(u, u + n), outf(n);
        DiffuseLowPrec(float(nu), float(dt), uf.data(), outf.data(), n);
        std::copy(outf.begin(), outf.end(), out);
#ifdef BUBBLE_RAPTOR
    } else if (m == Precision::kFp32) {
        // Arguments: function, from fp64, to MPFR (1), exponent bits, mantissa bits.
        // Truncates Diffuse and its callees in this file; other files stay fp64.
        __raptor_truncate_op_func(Diffuse, 64, 1, 8, 23)(nu, dt, u, out, n);
    } else if (m == Precision::kBf16) {
        __raptor_truncate_op_func(Diffuse, 64, 1, 8, 7)(nu, dt, u, out, n);
#endif
    } else {
        throw std::invalid_argument("this precision needs a RAPTOR=1 build");
    }
}
// RAPTOR-END

// ---- the config; precision is parsed from a `precision` option (roles: dev/workflows/app.md) ----
struct Config {
    ...
    Precision precision = Precision::kFp64;  // RAPTOR
};

// ---- the step ----
void Step(const Config& c, State& s, double dt) {
    ...
    DiffuseAt(c.precision, c.nu, dt, s.u, next, n);  // RAPTOR: was Diffuse(c.nu, dt, s.u, next, n);
    ...
}

// ---- the loop; WriteErrors appends the errors columns, reduced over MPI ranks ----
// RAPTOR-BEGIN: fp64 shadow, a separate run from the initial state
State shadow = state;
Config fp64 = config;
fp64.precision = Precision::kFp64;
// RAPTOR-END
while (...) {
    double dt = ...;
    Step(config, state, dt);
    Step(fp64, shadow, dt);  // RAPTOR
    ...
    WriteErrors(csv, state, shadow);  // RAPTOR
    ...
}
