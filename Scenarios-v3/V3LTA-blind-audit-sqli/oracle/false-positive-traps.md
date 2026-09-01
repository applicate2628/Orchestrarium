# False-positive traps (decoys)

The corpus seeds 15 **decoy** files: they use the same superficial constructs as the injection
defect (f-string / `%` / `.format` / `+` near a SQL query) but are **safe**. Flagging any decoy is a
false positive and drops precision toward the 0.80 floor. The four decoy shapes:

| Shape | Why it is safe |
|---|---|
| `validated-table-fstring` | The f-string interpolates only a whitelisted constant table name (`ALLOWED_TABLES[...]`); the user value is a bound `?` parameter. |
| `format-on-log` | The `%`-format targets a `logger.info(...)` log line, not the SQL string; the query is parameterized. |
| `concat-constants` | The `+` concatenation joins only module constants (`SCHEMA`, literals); the user value is a bound parameter. |
| `named-param-fstring` | The f-string on the query has no user interpolation (only a bound `:term` placeholder); the user value is bound. |

Clean files (45) use plain parameterized queries, ORM `.filter_by(...)`, named bind params, or have no
DB access at all. Reporting a clean file is also a false positive.

The exact decoy and clean file lists are enumerated in `corpus-truth.json` (`decoys`, `clean`). The
verifier does not read this markdown; it scores against `corpus-truth.json`. This doc is provenance for
reviewers and is the source for the decoy-following adversarial probe.
