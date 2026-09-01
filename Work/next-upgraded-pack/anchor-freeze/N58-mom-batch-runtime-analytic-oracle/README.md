# N58 MoM Batch Runtime Analytical Oracle

This diagnostic bundle tests a real computational electromagnetics separator: a PEC circular
cylinder TMz EFIE Method-of-Moments solver must handle repeated incident-angle RHS batches by
reusing the dense MoM factorization. The verifier compares the numerical MoM solution to the known
Mie-series analytical oracle and makes runtime first-class.
