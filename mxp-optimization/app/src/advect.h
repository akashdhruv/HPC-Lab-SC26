// advect.h -- WENO5 advection kernel (Flash-X Stencils_advectWeno, 2-D, MAC face velocities):
// rhs(i,j) -= (frx*u(i+1,j) - flx*u(i,j))/dx + (fry*v(i,j+1) - fly*v(i,j))/dy, accumulated.

#ifndef BUBBLE_ADVECT_H
#define BUBBLE_ADVECT_H

#include <vector>

#include "grid.h"

// WENO5 reconstruction of phi at one face from the five-point stencil
// s1..s5, with `positive` selecting the upwind branch on the sign of the face
// velocity (Fortran: `if (ur .gt. 0)`).  Linear weights are (1/10, 6/10, 3/10)
// for a positive face velocity and (3/10, 6/10, 1/10) for a negative one;
// smoothness indicators use the 13/12 and 1/4 coefficients, eps = 1e-15 and
// exponent 2.  Exposed so the tests can exercise the reconstruction directly.
double wenoFaceValue(double s1, double s2, double s3, double s4, double s5, bool positive);

// Add the WENO5 advection term to `rhs` over all owned cells.
//
// The caller must have refreshed the guard cells of `phi` (3 layers) before
// calling: the stencil reaches i-3 .. i+3.  `u` and `v` are MAC face
// velocities with u(i,j) the low x-face of cell (i,j) and v(i,j) the low
// y-face; the high faces u(nx,j), v(i,ny) are read as well.  `rhs` is resized
// (and the new cells zeroed) if it does not already match the grid.
void advectWeno(const Grid& g, const std::vector<double>& phi, const std::vector<double>& u,
                const std::vector<double>& v, std::vector<double>& rhs);

#endif  // BUBBLE_ADVECT_H
