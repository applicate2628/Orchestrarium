# Security Runtime Witness Review Task

Review the bounded target in `candidate/review-target/security-depth/` and write a JSON security
review report. Do not patch code, do not redesign the workflow, and do not edit files outside
`candidate/review-report.json`.

## Required Output

Write `candidate/review-report.json` with this exact top-level shape:

```json
{
  "contractId": "N89-security-review-runtime-witness-gauntlet",
  "findings": [],
  "falsePositiveAvoided": [],
  "witnessMatrix": [],
  "gateDecision": "REVISE"
}
```

Each `findings[]` entry must contain:

- `id`: stable finding id you assign (`F1`, `F2`, ...)
- `file`: bundle-relative file under `candidate/review-target/`
- `line`: single integer source line
- `category`: one of `authz`, `tenant-boundary`, `session`, `webhook`, `secret-exposure`, `pii`, `replay`
- `severity`: one of `high`, `medium`, `low`
- `title`: concise defect title
- `sourceEvidence`: source variable/function/sink binding
- `reproduction`: object with `caseId`, `attackerAction`, `observedImpact`, and `violatedInvariant`
- `fixBoundary`: one sentence naming the owner boundary that must enforce the fix

Each `falsePositiveAvoided[]` entry must contain `caseId`, `pattern`, and `reason`.

Each `witnessMatrix[]` entry must contain:

- `caseId`: one of `R1` through `R9` or `B1` through `B3`
- `status`: `reproduced` for exploit cases, `benign` for false-positive traps
- `observed`: object containing the exact concrete runtime values observed or ruled out
- `sourceBinding`: object naming the reviewed file, function, line, and sink or output boundary
- `findingId`: matching finding id for `R*` cases, or `null` for `B*` cases

## Review Inputs

- `inputs/review-boundary.md` - review scope rules
- `inputs/accepted-security-claims.md` - security invariants that must hold
- `inputs/trust-boundary-notes.md` - abstract authz, session, webhook, and exposure rules
- `inputs/repro-cases.md` - concrete exploit/benign probes to bind to findings or false positives
- `oracle/severity-anchors.md` - severity calibration

## Rules

- Report every concrete defect actually present in the reviewed code.
- Bind every real finding to the correct repro case from `inputs/repro-cases.md`.
- Bind every `R*` and `B*` case to an executable runtime witness row in `witnessMatrix`.
- Do not report benign probes as findings.
- Do not report cosmetic, stylistic, performance, accessibility, or UX observations.
- Every finding must cite a real source line in the reviewed file.
- `gateDecision` must be exactly `REVISE`.
