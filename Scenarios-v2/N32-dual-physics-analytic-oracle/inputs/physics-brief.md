# Physics Brief

## Electromagnetics

Model a perfectly conducting circular cylinder of radius `a` in two-dimensional TMz polarization.
The incident field is

`E_inc(x, y) = exp(i k (x cos alpha + y sin alpha))`.

The PEC condition is `E_inc + S rho = 0` on `r = a`, where `S` is the outgoing single-layer
operator with Green function `i/4 H_0^(1)(kR)`. The numerical solution must be a pulse-basis,
point-matched Method of Moments solve for the unknown surface density `rho`.

The verifier has two independent analytical checks:

- exterior total field from the exact cylindrical-harmonic series
- low-order Fourier coefficients of the exact surface density induced by the same operator

## Hydrogenic Radial Schrodinger

Use atomic units. For the reduced radial function `u(r) = r R(r)`,

`[-1/2 d^2/dr^2 + l(l+1)/(2r^2) - Z/r] u = E u`,

with `u(0) = 0` and `u(r_max) = 0`. The numerical solver should build the tridiagonal finite
difference Hamiltonian and select the requested bound state. The verifier compares against the
analytical hydrogenic energy and radial wavefunction.

Analytical formulas are validation oracles only. The candidate must solve the numerical systems.
