# Verifiers

Run from the bundle root:

```powershell
python verifiers/check_transport_report.py --mode template
```

`template` mode validates the seeded bundle shape, `scenario.yaml` contract keys, and the candidate
report schema.

```powershell
python verifiers/check_transport_report.py --mode completed
```

`completed` mode additionally requires the exact oracle-backed provenance values, review-strategy
values, and scope or fact snippets for the finished transport report.
