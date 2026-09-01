# Inputs

- `task.md` — the authoritative audit task and output contract. Follow it exactly.
- `corpus/` — 80 small handler modules (`h001.py` .. `h080.py`) to audit. They are audit **text**;
  they are never executed. Some contain the planted defect, some are safe-but-similar decoys, and
  most are clean.

The list of which files contain the defect is hidden from you (it lives in `oracle/`, which is not
part of your working copy). Audit the whole corpus.
