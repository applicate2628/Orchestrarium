# N32 Dual Physics Analytical Oracle

Repair one numerical physics workspace that contains two independent solvers:

- a fast pulse-basis Method of Moments solver for TMz scattering by a PEC circular cylinder
- a fast finite-difference radial Schrodinger solver for hydrogenic bound states

Both domains have analytical oracles used only by the verifier. The candidate must solve the
numerical problems directly, return machine-readable validation data, and keep all edits inside
the allowed candidate workspace files.
