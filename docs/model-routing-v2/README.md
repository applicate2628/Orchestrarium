# Adaptive Lead and Model Routing — Version 2

Status: main-aligned design and contract draft, not runtime implementation.
Historical audit baseline: main 68ad6e733e049ad3f86b37af59ea806e8d1a5b25 (2026-10-21).
Integration base: main cc570f2df858b7ab34a7922becc10fbc53f32b76; scope reconciled 2026-10-23.

## 1. Extend existing owners

Version 2 adds evidence-based comparison of eligible profiles and complementary
worker assignments, not a second orchestrator. The [ownership map](current-main-delta.md)
defines the integration boundary. Existing role/task policy supplies eligibility;
the existing Lead chooses whether to use a recommendation. Existing adapters,
review state, run ledger, lifecycle and publication owners remain authoritative.

Preserve quality, scope expansion, independent challenge, objective review and
whole accepted-result economics. A one-worker example is only the smallest case.
No automatic provider discovery, paid evaluation, fallback launch, new mutable
registry, duplicate ledger or universal graph executor is introduced.

## 2. Comparison is not execution

The first runtime slice is one pure function within the existing routing owner:
bounded explicit eligible candidates and constraints in; deterministic proposals
and evidence gaps out. It performs no I/O, persistence or launch.
Its in-memory signature belongs to that implementation slice after examining
the producer's actual eligibility output. No speculative new wire schema,
service or compatibility adapter is added by this documentation proposal.

Keep model identity, model-local effort, service tier and orchestration mode
separate. Model releases change dated input evidence and adapter requirements,
not universal model-name branches. Public benchmarks, API prices and subscription
quotas are not interchangeable; catalog presence is not admission.

Ordering remains: hard admission, quality, coverage, independent challenge,
evidence quality, accepted-result cost, latency, stable identity.
Unknown evidence is not zero cost or proof of quality. Conflicting evidence
cannot produce a selected recommendation. Recommendations never authorize
execution, weaken review or widen user permissions.

## 3. Two contract scopes

[Contract scope and ownership](contract-scope.md) maps every retained definition
and field to its responsibility and activation conditions.

- Initial comparison: current eligibility and work-item ownership. No fabricated
  lease, fencing token, terminal receipt or replacement state store.
- Deferred transferable-host protocol: the original schema bundles and examples
  keep all required lease/fence and settlement fields. They are NOT the
  input/output schema of the initial pure comparison function.

Validation keywords and parsed example records are preserved. Schema descriptive
metadata clarifies scope and current policy ownership; JSON cleanup only removes
trailing blank lines. Never remove a fence to make lease-free input validate.
Local locking is not proof of cross-host exclusivity. Future activation requires
lease acquisition, stale-epoch rejection, cancellation/revalidation, durable
recovery and independent concurrency tests. These guarantees are deferred, not
waived; current safety and receiving rules still apply.

## 4. Files and examples

- [Semantic bundle](adaptive-routing-contracts.v2.schema.json) and
  [semantic examples](examples.v2.json): retained transferable-host shapes.
- [Operational bundle](adaptive-routing-operational.v2.schema.json) and
  [operational examples](operational-examples.v2.json): retained execution/fencing
  envelopes. Examples are individual synthetic records, not an executable trace.
- [Runtime validation obligations](runtime-validation-obligations.md),
  [operational hardening](deep-review-operational-hardening.md) and
  [review conclusions](review-loop-closure.md): retained guarantees with explicit
  applicability, not a demand to rebuild current owners.
- [Profile evidence](effort-profile-evidence.md): effort/task/context binding.
- [Design](../superpowers/specs/2026-09-04-adaptive-lead-model-routing-v2-design.md)
  and [plan](../superpowers/plans/2026-09-04-adaptive-lead-model-routing-v2-implementation.md).
- [Legacy PR disposition](legacy-pr-disposition.md): retained responsibilities,
  superseded mechanisms and independent residual work.
- [Historical audit](../adaptive-model-routing-v2-audit-2026-09-04.md): prior
  evidence, not current-main qualification.

### Validating one declared record

These files are **definition bundles**, not root-level record validators. Their
`$defs` entries are inert until a caller selects the expected definition through
`$ref`. Passing an instance to a bundle root can accept even an empty object;
checking that the bundle is a valid schema checks the schema, not the instance.

After trusted acquisition, the consuming owner chooses the expected record type
from its own contract, never from an untrusted record's claim. This example uses
the same local-reference pattern as the tests and enables calendar-format checks:

```python
from jsonschema import Draft202012Validator, FormatChecker


def validate_record(bundle: dict, expected_definition: str, record: object) -> None:
    if expected_definition not in bundle["$defs"]:
        raise ValueError("unknown record definition")
    wrapper = {
        "$schema": bundle["$schema"],
        "$defs": bundle["$defs"],
        "$ref": f"#/$defs/{expected_definition}",
    }
    checker = FormatChecker()
    if "date-time" not in checker.checkers:
        raise RuntimeError("date-time format checker is unavailable")
    Draft202012Validator.check_schema(wrapper)
    Draft202012Validator(wrapper, format_checker=checker).validate(record)
```

For example, use `leadLease` with the semantic bundle and `dispatchControl` with
the operational bundle. An unknown definition is an error, not a fallback to root
validation. The already acquired bundle is trusted input here; this snippet does
not replace the bounded, duplicate-key-rejecting reader required by
[runtime validation obligations](runtime-validation-obligations.md#4-snapshot-and-digest-trust).
The environment must supply the `date-time` checker and its optional dependency;
merely constructing `FormatChecker()` does not establish that this check exists.
The example refuses a missing checker instead of accepting unchecked dates.
It validates local record shape only, not cross-record consistency, admission, or
authority to launch. The snippet is tested directly from this guide.


## 5. Integration and acceptance

Focused tests require pytest, jsonschema and its RFC 3339 date-time checker
(for example rfc3339-validator). A bare jsonschema installation may silently
omit date-time validation. The documented validator refuses that environment;
a failed calendar test is not waived or counted as a pass. Provision dependencies
through the repository's authorized development environment before a full run.


Build on pinned current main, preserving its index and release log. Do not merge
old branches wholesale or close them before each meaningful change is resolved.
Retained schema tests check record invariants; documentation tests check owner
reuse and scope. Neither proves running routing, adapter support or host transfer.
Record unrun checks and missing independent review on the final candidate.

## Terms and Abbreviations

Lead: accountable orchestration owner. Admission: permission for a bounded action.
Profile: model, effort and execution configuration. Lease/fence: transferable
ownership and stale-owner rejection records. I/O: input/output effects.
API: application programming interface. PR: pull request.
