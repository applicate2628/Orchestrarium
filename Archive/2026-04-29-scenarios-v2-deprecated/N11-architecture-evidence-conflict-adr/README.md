# N11 Architecture Evidence Conflict ADR

Produce a conflict-aware ADR from accepted inputs. Edit only `candidate/design-package.md`.
The hardened contract requires explicit evidence-binding and forbidden-direction tables so source
specificity and adapter-boundary discipline are machine-checkable.

Run:

```powershell
python verifiers/check_architecture_evidence_conflict.py
```
