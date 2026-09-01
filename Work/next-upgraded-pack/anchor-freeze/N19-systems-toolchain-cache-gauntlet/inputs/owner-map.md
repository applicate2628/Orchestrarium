# Owner Map

| Surface | Owner | Boundary |
|---|---|---|
| profile/env precedence | `config.py` | normalize settings before planning |
| path validity and normalization | `paths.py` | no caller-side path patches |
| cache key semantics | `cache.py` | deterministic and portable |
| dependency order | `planner.py` | plan owns topological sequencing |
| lock lifecycle | `lockfile.py`, `executor.py` | release in success and failure paths |
| source trace reporting | `report.py` | derive from ledger events |
