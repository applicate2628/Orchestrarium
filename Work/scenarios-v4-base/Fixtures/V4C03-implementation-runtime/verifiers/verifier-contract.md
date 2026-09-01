# V4C03 Verifier Contract

Five observable cases score independently. Interface and changed-path sets use F1, so an omission or
extra path changes only its set atom. The focused test result is separate. Provider runtime, token
counts, and transcript size are never score inputs. Narrative is ignored.
The visible schema permits integer or string HTTP outcomes. Each R1-R5 rubric atom explicitly treats
finite numeric strings as equivalent to its integer status, including decimal and exponent spelling;
nonnumeric and non-finite strings remain incorrect.

Scorer-side faults return `SCORER-ERROR` with no numeric score.

## Terms and Abbreviations

- `F1`: harmonic mean of precision and recall.
