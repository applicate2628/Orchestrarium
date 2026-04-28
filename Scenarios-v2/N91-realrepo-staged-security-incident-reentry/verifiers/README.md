# Verifier

Run:

```powershell
python verifiers/check_staged_security_incident.py --bundle-shape-only
python verifiers/check_staged_security_incident.py --expect-start-state
python verifiers/check_staged_security_incident.py
```

The verifier protects service/model contracts, runs visible tests, executes
hidden incident probes, checks staged ledgers, and enforces exact changed paths.
