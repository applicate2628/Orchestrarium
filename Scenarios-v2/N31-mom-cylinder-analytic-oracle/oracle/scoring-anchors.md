# Scoring Anchors

Use the scientist/numerical role-fit profile, but treat these as N31-specific signals:

- PASS requires a Method of Moments density solve, not only analytic field samples.
- PASS requires the candidate density to satisfy an independently rebuilt boundary residual.
- PASS requires exterior field samples to match the cylindrical-harmonic analytic oracle.
- PASS requires convergence from `64` to `96` panels on the public case.
- PASS requires a hidden non-default radius, wavenumber, and incidence-angle probe.
- Runtime is part of the role-fit read: a correct but very slow dense solver is weaker.
- Missing validation report or notes is a scoreable artifact failure, not a runtime failure.
