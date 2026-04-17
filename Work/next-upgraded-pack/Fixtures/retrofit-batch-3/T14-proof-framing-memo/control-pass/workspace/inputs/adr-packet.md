Proof packet

Required invariants:
- the archive remains frozen
- the scratch `broken/` copy is the only mutable run root
- a row pass requires local verifier success
- ranking changes require execution-backed evidence

Forbidden shortcut:
- do not count blocked or unrun tests as failures
