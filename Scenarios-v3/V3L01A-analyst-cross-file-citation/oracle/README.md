# Oracle

`citation-contract.json` binds each confirmed fact to the AUTHORITATIVE source (`config/effective.py`)
at an exact line with the effective value, requires the three mis-cited sources (declared defaults x2 +
legacy doc) to be explicitly rejected, and requires two explicit unknowns. `scoring-anchors.md` gives
the PASS conditions and the near-peer separation argument. `reference/` holds a passing answer.

Not staged to the provider-visible root. The verifier reads text only (executes nothing).

Near-peer separation: the wrong citation is PLAUSIBLE - the value 3 literally appears in defaults.py and
the legacy doc - so a near-peer analyst that cites the surface definition mis-cites (wrong File and wrong
value), while a top analyst traces the override to effective.py (value 5 / 8000 / batch) and rejects the
surface sources. The File+value binding plus the mandatory rejection table is the discriminator.
