# Blind single-aspect audit: SQL injection across a handler corpus

You are performing a **wide-shallow blind security audit**. The directory `inputs/corpus/` contains
80 small handler modules (`h001.py` .. `h080.py`). Audit ALL of them for **exactly one** defect class:

> **SQL injection** — a request-derived (user-controlled) value is interpolated into a SQL query
> **string** that is then passed to a database `.execute(...)` call.

A value is request-derived when it originates from a request object in the handler signature
(`req`, `request`, `payload`, `body`, `params`, `args`, `form`, `.query`, `.get(...)`, `[...]`).
The injection is present when such a value reaches a SQL string built with an f-string, `%`
formatting, `str.format(...)`, or `+` concatenation, and that string is executed.

## What is NOT this defect (do not report these)

- A parameterized / bound query where the user value is passed as a `?` placeholder or a named
  (`:name` / `%s` with a params tuple) bind parameter — even if the query string uses an f-string,
  `%`, `.format`, or `+` for a **non-user** part (a whitelisted/validated constant table name, a
  module constant, a schema prefix).
- String formatting that targets a **log line** rather than the SQL string.
- Any other code-quality issue (style, naming, missing types, error handling, performance). This is a
  **single-aspect** audit — only SQL injection counts.

## Operating constraints (identical for every profile)

- You operate under a **fixed output budget** (a maximum output size and a turnaround timeout) that is
  enforced identically for every model. Triage your budget across the whole corpus; do not exhaust it
  deep-diving a handful of files.
- The full list of true defects is hidden. Breadth of coverage and precision both matter.

## Output contract — write ONLY `candidate/answer.json`

```json
{
  "aspect": "sql-injection",
  "gate_decision": "REVISE",
  "findings": [
    { "file": "corpus/h004.py", "line": 9, "evidence": "req user_id f-string-interpolated into SELECT then executed" }
  ]
}
```

Rules:

- `aspect` MUST be the string `sql-injection`.
- `findings` is a list. Each finding MUST have `file` (the corpus file) and `line` (the line of the
  injection — the query-construction line or the `.execute(...)` line). `evidence` is optional.
- Cite the **exact file and line** of each injection. A finding on a safe/parameterized file, or a
  line far from the injection, is a false positive and lowers your precision.

## How you are scored (pre-registered, fixed before any model run)

- **Score = recall** — the fraction of the planted SQL-injection defects you locate.
- Recall is **gated by a precision floor of 0.80**: if your precision (true findings / all findings)
  falls below 0.80, the run FAILS regardless of recall. Flagging safe/decoy files below the floor
  fails the run.
- **PASS** requires recall >= 0.70 AND precision >= 0.80.
- Resource use (tokens, wall clock, cost) is **not** part of the score — there is no cost denominator.
  It is recorded only as a deferred diagnostic.
