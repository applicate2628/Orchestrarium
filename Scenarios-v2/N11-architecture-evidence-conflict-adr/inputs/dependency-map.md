# Dependency Map

Allowed dependency direction:

`agents-mode loader -> normalized profile catalog -> external-worker / external-reviewer adapters`

Forbidden direction:

`external-worker / external-reviewer adapters -> lane taxonomy or profile parsing`

Required boundary:

The secret-backed `X4` Claude route is runtime transport resolution carried through `providerRoutes`.
It must not become a key in `externalPriorityProfiles`.
