# Verifier

Run:

```powershell
python verifiers/check_staged_interface_reentry.py --bundle-shape-only
python verifiers/check_staged_interface_reentry.py --expect-start-state
python verifiers/check_staged_interface_reentry.py
```

The verifier protects immutable bundle inputs, runs visible tests, executes hidden SubscriptionMesh
runtime probes, performs a clean-room public package import, checks staged source/reentry ledgers,
and enforces exact changed paths when supplied by the runner.
