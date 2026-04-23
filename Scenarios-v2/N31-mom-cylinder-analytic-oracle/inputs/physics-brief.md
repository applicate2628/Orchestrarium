# Physics Brief

Model a perfectly conducting circular cylinder of radius `a` in two-dimensional TMz
polarization. The incident field is a unit-amplitude plane wave:

```text
E_inc(x, y) = exp(i k (x cos(theta_i) + y sin(theta_i)))
```

The PEC boundary condition is:

```text
E_inc + E_scat = 0 on r = a
```

The outgoing two-dimensional Green function is:

```text
G(r, r') = i/4 H_0^(1)(k |r - r'|)
```

The MoM unknown is the scalar single-layer density on the cylinder boundary:

```text
integral_Gamma G(r_i, r') sigma(r') ds' = -E_inc(r_i)
```

The analytic oracle is the exact cylindrical-harmonic series:

```text
E_scat(r, phi) = sum_n b_n H_n^(1)(k r) exp(i n phi)
b_n = - i^n exp(-i n theta_i) J_n(k a) / H_n^(1)(k a)
```

The oracle is used only for validation. The candidate must solve the boundary integral
equation numerically by Method of Moments and return the surface density.
