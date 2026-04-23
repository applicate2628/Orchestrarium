# Decoy Map

| Path | Decoy | Correct handling |
|---|---|---|
| `candidate/workspace/docs/stale-plan.md` | claims `legacyProfile` wins during freeze windows | reject as stale |
| `candidate/workspace/legacy/report_old.py` | builds reports from notification history | reject as archived helper |
| `candidate/workspace/ui/status_badges.py` | exposes visible badge labels | leave untouched; UI does not own report source |
