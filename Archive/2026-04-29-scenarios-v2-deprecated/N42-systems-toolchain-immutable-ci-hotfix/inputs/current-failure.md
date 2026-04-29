# Current Failure

The live staging worker is using old channel selection and unstable fingerprints. Operators report
that cache restores sometimes rebuild the same artifact on different machines, while failed staging
attempts leave a lease behind and block the next retry.
