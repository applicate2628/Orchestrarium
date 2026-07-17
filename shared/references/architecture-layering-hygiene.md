# Architecture layering hygiene — generalized best practices

Maintainer source-of-truth (read on demand; NOT installed to targets). The compact, decidable form
ships in the `$architect` and `$architecture-reviewer` role definitions, which cite this file.
Generalized — provider / domain / language-agnostic; the laws are stated as decidable tests, not
slogans, and each names the OWNER it protects plus the ENFORCEMENT PROBE that catches a violation.
Synthesized from a layer-library architecture rule (a numerical-solver repo) and stripped of its
domain specifics (FEM/MoM, CMake, strict-FP byte-gate); only the generalizable core remains. The
laws state DEFAULTS with named exceptions — apply them as pressure tests, not absolutes (an
over-absolute reading produces false findings).

## The principle

Split a system into MODULES by responsibility LAYER, each a single-owner unit with a narrow
interface, and compose them — NOT into big independent per-feature programs that each privately copy
the shared layers (a "silo"). A feature / variant / scenario is a THIN ASSEMBLY over the shared
layers, never a fork of them. This applies to ALL abstraction levels: every layer is itself a
single-owner unit whose consumers (including higher layers and feature scripts) stay thin. The
payoff is FOUR properties, which organize the rest of this file:

- **Generalization / scaling** — new cases land as thin compositions, so the system scales to new
  scenarios without forking the stack.
- **Performance** — boundaries are stable and collapsed only under measurement, so abstraction never
  silently costs speed and optimization stays safe.
- **Stability / reproducibility** — single ownership of capabilities and cross-cutting invariants
  means a change stays in its blast radius and results stay consistent, and a change leaves the live
  tree asserting only its correct current state (C6).
- **Runtime / operational behavior** — failure, observability, reproducibility, resource lifetime, and
  concurrency are owned at the right ring, so a module stays embeddable, observable, reproducible,
  leak-free, and race-free under execution.

These SHARPEN, not replace, the always-on spine rules. The spine rule each one extends is tagged
inline as `[spine: <rule>]`; an item with no tag is net-new.

## The abstraction-level meta-law (anchors the structural laws A1–C5)

**M — Right abstraction level: abstract by default, concretize ONLY where genuinely required.** Every
owner — a type, contract, function, module, registry, scenario, or even a law — is defined at the MOST
GENERAL level its responsibility allows; a concrete specific (a particular value, method, case type,
scenario, parameter, variant) lives ONLY in the leaf / adapter / instance / injected-config that
genuinely needs it, and is NEVER lifted into the general owner. Where concreteness is not needed the
form stays ABSTRACT and PARAMETERIZED (a type/strategy parameter, a contract port, a registry entry, an
injected config field) so a new concrete case is a NEW INSTANCE, not an owner edit. This is the
discipline behind the structural laws below — e.g. a generic engine names no consumer, the adapter is
the edit surface while the backend stays stable, a new variant is a plugin not a silo, config is
injected not read (the A/C laws are its instances; read it as the frame, the forward names are
illustrative not load-bearing). M ANCHORS the structural laws A1–C5 — the laws whose shape it explains
(C6 is a stability/live-tree-consistency law, NOT a structural one M anchors); faithful to source L16
(anchors only the structural laws), M does NOT extend its anchor over the runtime group D. FALSIFIABLE
TEST: if adding or changing a concrete case FORCES editing a GENERAL owner, the abstraction level is
WRONG — push the specific DOWN and keep the owner general (an owner edit forced by a new instance is the
churn metric). NOT "abstract everything": OVER-ABSTRACTION — an indirection layer with no second
instance and no churn-test justification (a one-implementation interface, a strategy with one strategy,
a config knob nobody varies) — is the OPPOSITE, equally-flagged failure. Abstract EXACTLY to the level
the responsibility needs. OWNER: the author of each general owner (its abstraction level) + the reviewer
(the abstraction-level judgment). PROBE (partial, review-bound): the extension-churn budget mechanically
catches the under-abstraction side — a new concrete instance that forces a general-owner edit FAILS; the
over-abstraction side and the abstraction-level judgment are a review verdict, not a grep. [spine:
General-case over local symptoms, SOLID reminder]

## A. Generalization & scaling

**A1 — Ownership follows the dependency graph, not a name or level label.** A capability is owned by
the LOWEST module that can express it depending only on modules below it. The actual dependency edges
(imports / requires / link edges) are the authority; numeric "level" or directory NAMES are a
non-binding reading aid (A1 thus *inverts* directory-by-name organization — edges over names). An
upward or cyclic dependency must be CAUGHT BY A REPO-STANDARD GATE configured to fail — a build, a
lint/import-graph check, a validator, or CI (whichever the ecosystem can enforce; not every language
fails the build on a cycle). That gate, not a convention, is the enforcement. [spine: SOLID reminder,
Ownership / extension-seam hygiene]

**A2 — The adapter is the edit surface; the backend is stable BY DEFAULT.** Add a new scenario,
method, or integration by EDITING the thin binding layers — composition (wiring), coupling, and the
interface-leaf ADAPTERS — first, NOT by reaching into a stable backend module. To support a new case
you should usually be editing an adapter / composition / interface; the backend should not need a
scenario-specific change. EXCEPTION: a backend edit is legitimate when the new case exposes a MISSING
GENERALIZED capability or a misplaced seam — provided the edit generalizes (is not scenario-specific)
and existing consumers stay protected. The smell is a *scenario-specific* backend edit; that means
the seam is missing or misplaced — add or move the adapter, do not fork the backend. (Universality
corollary of A6: A6 says WHERE the contract lives; A2 says the adapter on top is what you edit.)
[spine: Ownership / extension-seam hygiene, Change-surface minimization, Blast-radius test]

**A3 — A generic engine names no specific consumer.** A reusable engine / service / utility depends
only on its abstract inputs and names no specific feature/method in its symbols, imports, or
dependency edges. It takes an abstract input (an assembled structure, an `apply`/strategy callback, a
typed request) and returns a result. A new consumer becomes a thin script by SUPPLYING that input —
never by adding a variant of the engine or a method branch inside it. [spine: SOLID reminder]

**A4 — A new variant is a plugin + thin scenario, never a parallel silo.** A new feature / method /
variant extends the EXISTING modules via a plugin at the right layer plus a thin scenario over the
existing seams. It must NOT spawn a parallel copy of the whole stack. If a "new variant" needs its
own copy of shared infrastructure (its own parse / storage / transport / geometry copy), the layering
is wrong — the seam it should have composed is missing. [spine: Blast-radius test, Reuse before
hand-rolling, Mechanism inventory before new paths]

**A5 — "Thin" is defined against a layer, not line count: the second-consumer test.** An entry point
(CLI / app / handler / job) owns PROCESS-BINDING only — argument / env / file / exit / IO policy.
Every decision that survives a change of entry point — selection, sizing, strategy choice, sweep /
retry control, result gating — is library capability and lives in a library. The test: if a SECOND
entry point (a tool, a test, a future GUI) would need the same decision, it is NOT wiring — it belongs
in a library. [spine: Change-surface minimization, Ownership /
extension-seam hygiene]

**A6 — Dependency inversion: the contract goes on a stable surface, never reversed.** When a lower
module must be INVOKED by, but cannot DEPEND ON, a higher module, define the narrow CONTRACT on a
STABLE surface that both sides may depend on without reversing dependency direction — the lower module
itself, or a neutral contract / interface module below both — and INJECT the implementation from
above. The contract does NOT always live "in the lowest module": service contracts, plugin APIs,
schema registries, and role/agent contracts often live on a neutral stable surface both sides import.
The invariant that DOES hold everywhere: implementation-heavy / private modules must NOT be imported
across layers — cross-layer consume is legal only against an interface leaf with no downward edges; an
edge into a sibling's private/internal module across a band is presumptively a silo leak. [spine:
Interface and encapsulation hygiene, SOLID reminder]

**A7 — Split a capability by level BEFORE calling anything a copy (graduate-the-core).** Decompose a
capability by abstraction level. The lowest pure, dependency-light CORE (no feature / transport /
storage deps) is the single-owner unit and MUST be reused (imported / referenced / generated from one
source), never re-typed by hand. Consumer-level orchestration of that core over a specific layout is
per-consumer GLUE — not a copy — but it must CALL the core, never re-derive it. A "production must not
depend on a sandbox / experiment" need is satisfied by GRADUATING the core to its owning module FIRST
(so production reuses the graduated core), NEVER by re-implementing it to dodge the dependency.
Re-implementing a graduated core "to avoid the dependency" is a defect, not isolation. (Hard-boundary
exception: see C1.) [spine: No logic duplication / no fix layering, Reuse before hand-rolling]

## B. Performance

**B1 — A boundary is a link/call boundary by default; collapse it for SPEED only under measurement.**
A seam is a link/call boundary by default. Collapsing / inlining a seam FOR PERFORMANCE is allowed
ONLY when (a) a PROFILE MEASUREMENT shows it on a measured-critical path AND (b) the collapsed unit
stays a single coherent owner — its ownership, lifecycle, resource cleanup, contracts, and tests
remain inside one module. Never collapse a seam for speed speculatively ("this might be faster
inlined" without a measurement is a violation, not an optimization). This governs PERFORMANCE-MOTIVATED
collapse only — ordinary refactors that move code for clarity are governed by A1/A2, not B1. Absent
the measurement, the core stays OWNED by the layer holding the loop and the seam stays coarse. [spine:
Pre-fix diagnostic gate (profile before changing a working path for speed)]

**B2 — Do not split a measured-critical or order-sensitive sequence across a boundary.** A hot inner
loop, an order-sensitive reduction / accumulation, a single transaction, or a streaming pipeline stage
stays in ONE unit; the seam sits at its input / output, never mid-sequence. Splitting it across a
boundary both costs performance and (for order-sensitive reductions) can change results — see C1.

**B3 — Thread heavy context at coarse boundaries only.** Execution context, handles, connections, and
large config are passed at COARSE public boundaries, never re-threaded per inner iteration (record /
row data flowing through a pipeline is not "heavy context" — this is about ambient handles, not
payload). Per-iteration context plumbing is both a performance cost and a coupling leak.

## C. Stability & reproducibility

**C1 — One owner for a cross-cutting invariant.** A cross-cutting invariant that must stay globally
consistent — a mode predicate (e.g. a deterministic / strict mode), a canonical ordering, a shared
constant, the meaning of a feature flag, a calibration table — has EXACTLY ONE owner that every
consumer CALLS. No module re-decides it, and no module re-defines or re-types it "to stay consistent"
— that re-definition IS the bug (the copies drift). HARD-BOUNDARY EXCEPTION: a duplicated
*representation* across a process / language / ABI / generated-code / database-schema / external-
protocol boundary is allowed ONLY when it is derived from one owned source (codegen, a shared schema)
or guarded by a drift / contract gate that fails on divergence; unchecked hand re-typing across such a
boundary remains the bug. Reproducibility (bit-identical or contract-identical results) depends on
this single ownership. [spine: No logic duplication / no fix layering]

**C2 — Config and control-flow are upper-layer inputs: parse once at the top, inject down.** Process
environment, command-line options, deck / scenario selectors, validation labels, file paths, and mode
switches are UPPER-LAYER inputs. The top (app / composition / handler) parses them ONCE into typed
immutable config structs, execution-policy objects, or strategy callbacks, and passes already-resolved
values DOWN. A lower module reading `getenv` / command-line policy / a global scenario mode is an
UPWARD CONTROL-FLOW LEAK even when no dependency edge exists. The only exception is documented
diagnostic / observability instrumentation with no business, semantic, output, persistence, security,
or control-flow effect, owned by a support / observability layer — never ordinary lower-layer domain
logic. [spine: Determinism and ambient-input control, Anti-hardcoding]

**C3 — Backend stability is a stability property (same seam as A2).** Backend modules (foundation,
generic engines, storage, transport) absorb new scenarios through adapters / composition (A2); a
*scenario-specific* backend edit widens the blast radius of every future change. This is the stability
reading of A2 — when these condense into the role rules, A2 and C3 are ONE rule with a two-outcome
annotation (generalization + stability), not two checks. [spine: Change-surface minimization,
Blast-radius test]

**C4 — Shared test support is a single-owner, test-only module.** Generic test / validation support —
fixtures, structured generators, golden-artifact loaders, reference solutions, generic harnesses — is
a single-owner unit under a TEST-ONLY tree, parameterized over the PRODUCTION CONTRACT (an interface,
not a concrete impl), isolated from production targets, and NEVER homed inside one implementation's
tests. Consequence: removing or demoting an implementation must be a PURE DELETE with zero edits to
other implementations' tests. Falsification: if a test-support file is imported / linked by
implementation B's tests while living under implementation A, it is mis-homed. (Genuinely net-new — no
spine rule names test-support ownership.)

**C5 — Grandfathered debt is tracked, never silently re-blessed.** Accepted current debt that a
documented decision explicitly blesses (an "example adapter," a temporary copy) is distinguished from
the rule for NEW work. Record it as a grandfathering entry naming the OWNER, the SCOPE, the
EXPIRY / review trigger, and explicit "no expansion" language; track open violations in a ranked DRIFT
BACKLOG separate from the rule. A grandfathered item is NEVER a license for new violations of the same
shape, and tracked in the repo's decisions / grandfathering registry where one exists. [spine: Hypothesis disclosure discipline (WORKAROUND labeling)]

**C6 — A superseding change leaves only the correct current state; stale-relation residue is erased.**
When a change makes a prior state obsolete — a rename, split, merge, completed deprecation, entity
move/delete, or a design/bug fix that supersedes old behavior — the LIVE TREE (code, comments, docs,
names, identifiers, registry entries, config, active task/work items) must reflect ONLY the correct
CURRENT state. The decidable DELTA this law adds over the spine's file-level hygiene ([spine: Trash
hygiene and archival] deletes superseded FILES) AND over forward-update hygiene ([spine: Canonical-source
maintenance discipline] updates the OWNING canonical doc forward) is the STALE-vs-LIVE RELATION
DISCRIMINATOR applied to names/aliases/comments/registry entries + the post-change grep-for-the-old-name
probe: a STALE relation asserts an OBSOLETE relationship (the rename is done, the alias is gone, the
misregistration is fixed) → ERASE it; a LIVE relation asserts a CURRENT fact (a real dependency, a
deliberate split, a measurement/comparison true today) → KEEP it. Residue to erase: `X→Y alias`,
`X (was Y)`, `former X`, `X = deprecated alias`, `used-to-be-misregistered-as`, `now-retired, kept as a
historical example`, `this is wrong, the correct is Y` (leave only Y), dead pointers to moved/deleted
files, stale paths. Do NOT blindly delete every co-mention of the old name — that destroys legitimate
LIVE relations; delete only where the asserted relationship is obsolete, and VERIFY each deletion leaves
a correct current statement. The fix's provenance lives in version control + ONE record in the repo's
decision/closure registry (e.g. `work-items/decisions/` or the work-item's `closure.md`) — never
scattered inline as "fix-over-fix-over-error" archaeology. C6 lives in group C because the live tree's
current-state correctness is a STABILITY/reproducibility property (stale residue drifts the source of
truth and breeds fix-over-fix bugs) and it pairs with C5 as the change-hygiene complement: C5 TRACKS
blessed current debt, C6 ERASES superseded residue. Erasing stale-relation residue also removes a class
of leaked-historical-identifier residue — a former internal name, a retired credential identifier, a
dead secret-bearing path is a LEAK to erase ([spine: Publication safety]). OWNER: the author of the
superseding change (the live tree's current-state correctness). PROBE: after any superseding change,
grep the live tree for the old name + the stale-relation phrases above; each hit is removed (verifying
the removal leaves the correct current statement) or justified as a LIVE relation. The stale-vs-live
discrimination is review-bound — the grep surfaces CANDIDATES, a reviewer verifies each hit is truly
obsolete before erasing. A fix that leaves stale-relation residue is incomplete. [spine: Trash hygiene
and archival, Logic-revision discipline, Canonical-source maintenance discipline, Hypothesis disclosure
discipline (clean self-introduced churn before push)]

## D. Runtime & operational behavior

A1–C5 govern WHERE code lives and HOW it is extended (structure); C6 keeps the live tree's current state
consistent after a change (stability). D1–D5 govern how it BEHAVES under execution — how it fails,
reports about itself, records provenance, owns lifetime, and shares data across parallel boundaries.
Same form as A-C: decidable tests with a named owner + enforcement probe, defaults with named
exceptions, SHARPENING the tagged spine rules.

**D1 — Failure is a typed RETURNED value; process termination is composition-root-owned.** A reusable
module (library, leaf, engine, service component) reports failure as a typed RETURNED status/error value
carrying SEVERITY, a STABLE failure ID, and an optional CAUSE CHAIN — never by invoking a
process-termination primitive (`exit`/`abort`/`_exit`/`std::terminate`/`os.Exit`/`System.exit`/a panic
that aborts the process). ONLY the composition root / app entry point owns process termination; on a
fatal-severity returned failure IT makes an EXPLICIT termination / degradation / recovery decision (the
severity is the input to that decision, not an implicit exit). A leaf that kills the process is
UNEMBEDDABLE (in-process UI, API host, test harness, a second instance in one process) and erases the
caller's diagnostic context. This is fail-loud UP the call chain, not by killing every other caller. The failure idiom is chosen per LAYER and is uniform within it: process exit at the composition root; typed returned status from libraries/leaves; an in-band poison value (e.g. NaN-poison) ONLY where no status channel exists (a numeric kernel with no side-band), documented at the contract. The
three fields are load-bearing: severity → response choice; stable failure-id → a machine key for
tooling/tests; cause chain → originating context. The severity must distinguish at minimum the response
classes the composition root can select (e.g. recoverable / degrade / fatal). (Source L11: leaves NEVER
terminate; only the composition root does — a genuine fail-stop on detected state corruption /
memory-safety violation is the composition root's decision on a returned typed failure, or an explicit
documented composition-root contract, never a leaf license.) OWNER: the composition root (process
lifetime + the recovery decision) + the caller (diagnostic context). PROBE: grep the reusable-module
tree — the modules/libraries/packages explicitly DESIGNATED reusable (not composition roots, app entry
points, or test-binary harnesses; the repo-local governance defines the boundary, as A1's probe defers
to "the repo-standard gate"; where no boundary is declared, the scope is every source file NOT at an
entry point (not `main.*`, not in an entry dir such as `cmd/`/`bin/`/`app/`) and NOT a test binary — a
binary scope the reviewer records) — for termination primitives; a NEW occurrence in this change FAILS;
the existing baseline is a frozen debt that only decreases — a repo CI counter where one is configured,
else the probe is review-bound (the reviewer counts new termination primitives in the diff); idiom-uniformity: two failure idioms for one failure class within one layer is a finding (review-bound). [spine:
Failure transparency and diagnosability, Operational-contract scope discipline]

**D2 — Observability is one support-owned, injected diagnostic port with stable event IDs and a
zero-cost disabled path on measured loops.** Diagnostics (trace, progress, profiling, correlation,
structured logging) flow through ONE support-layer-owned diagnostic PORT, INJECTED from above (dependency
inversion, A6-shaped) and threaded at a COARSE boundary, never re-passed per inner iteration on a
measured loop (B3); it carries STRUCTURED events whose IDs come from a single CONST registry. The IDs are
a VERSIONED API CONTRACT — downstream log/trace/alert tooling depends on them. On a MEASURED/hot path the
disabled path is COMPILE-TIME-ELIDABLE — when off, the hot path carries NO residual branch, call, or flag
load. A per-iteration check on a RUNTIME variable flag is insufficient there (it costs the flag load and
can block vectorization); a build-time-constant-false guard the optimizer folds away, or a compose-time
non-instrumented path, is fine — the requirement is ZERO RESIDUE in the measured loop body, however
achieved. Off measured loops a runtime-gated no-op is fine. This is the positive shape of C2's
diagnostic-instrumentation exception — it does NOT restate C2's ambient-read ban nor C1's
single-owner-registry rule (cross-reference both); its net-new delta is the single injected port + const
ID registry + versioned-ID contract + compile-elision-on-a-measured-loop (adjacent to but not a
restatement of B1/B3). EXCEPTION: a non-performance-critical module may use a runtime-gated port
everywhere; a runtime that cannot elide (interpreted / JIT with no zero-cost abstraction) hoists the
enable-check OUT of the hot loop or selects a compose-time non-instrumented path and records the
limitation. OWNER: the support/observability layer (single diagnostic channel + versioned event-ID
registry; the PROBE is facet-split across slices — impl owns the structural route-through-the-port part,
perf owns the compile-elision residue check — mirroring how D3's OWNER flags its security-engineer
facet). PROBE: (1) no diagnostic free-text emit or ambient env read for diagnostics outside the support
owner (grep); (2) every emitted ID resolves in the const registry (fail-closed); (3) on a compiled
measured path the disabled-residue check is STRUCTURAL first — the diagnostic owner is NOT in the
link/import set of the measured unit, OR the disabled path is a build-time constant the compiler provably
folds (both checkable from the build/link graph); ONLY where the perf budget explicitly demands the
zero-residue proof, inspect the IR/asm of the RELEASE/optimized build (a debug build is not the binding
artifact) confirming no branch/call/flag-load from the diagnostic owner; on an interpreted/JIT runtime
taking the exception this is review-bound (the enable-check is structurally outside the loop or a
non-instrumented path is wired — no asm/IR to inspect). BINARY SELECTOR: if no repo-defined perf-budget
gate names the path budget-critical, the structural-link check is the BINDING probe (asm/IR escalation
applies ONLY when a perf-budget gate explicitly demands it); structural-link ALSO requires absence from
the measured unit's INCLUDE/macro-expansion set (no header-injected diagnostic), not only its link set;
in a repo with NO machine-readable build/link graph (interpreted, no static import graph) the check is
review-bound. [spine: Determinism and ambient-input control, Interface and encapsulation hygiene]

**D3 — Reproducibility is a publication-safe manifest contract (run provenance), broader than output
equivalence.** Every result-producing run EMITS a machine-readable MANIFEST recording the run PROVENANCE
needed to reproduce it: toolchain + build flags; PINNED dependency versions (an exact version/hash, never
a moving tag/branch/`latest`); host/runtime platform identity (OS + math/standard-library version + CPU
ISA/microarchitecture class where numeric output depends on it); determinism / numeric mode (including
floating-point contraction/FMA and rounding posture where the toolchain exposes it); random/seed state
for any stochastic step; parallel/concurrency configuration (worker count, scheduling/affinity, AND the
reduction partitioning — grain/chunking — that determines a floating-point reduction tree, so a
bit-identical FP result reproduces only within a fixed partitioning, per D5); input identities (labels +
content HASHES); a config/environment SNAPSHOT; contract/schema versions; the selected strategy/algorithm.
Result-producing, golden, and validation/release artifacts MUST carry it; a MISSING manifest, a DIVERGENT
manifest (from the prior accepted baseline — the first manifest establishes the baseline), or one
SILENTLY OMITTING a required field, FAILS packaging — an EXPLICITLY-ABSENT field (recorded
absent-with-reason) passes (the discriminator: silent omission fails, declared-absent passes). Manifest
emission is FAIL-CLOSED: a partial or failed emission BLOCKS promotion. This is BROADER than OUTPUT
EQUIVALENCE — bit-identical or contract-identical output where that is the contract (C1 owns output
equality via single ownership; boundary: "C1 = the result is equal; D3 = the run that produced it is
recorded and reproducible") and catches the moving-dependency-drift class output-equality alone cannot.
The env/config snapshot is ALLOWLIST-BUILT and PUBLICATION-SAFE in two ordered layers: (1) PRIMARY,
default-closed — capture ONLY an explicit allowlist of build/determinism-relevant variables; ANY key not
on the allowlist is excluded, and a non-allowlisted key reaching the snapshot is a packaging FAIL; (2)
BACKSTOP — the captured allowlisted VALUES are scanned by TWO distinct detectors: (a) a
machine-local-path / user-home VALUE → the publication-safety machine-local-path signal; (b) a
credential / license / token VALUE → a separate secret-pattern detector (one detector does not cover both
classes). The gate MUST run BOTH detectors over EVERY emitted allowlisted value; if a detector is
unavailable the manifest does NOT emit (fail-closed). Layer-2's default-safe disposition is EXCLUSION
(drop the value); REDACTION is a review-bound, named-owner exception for a value on an allowlisted key
whose presence is itself required — never an automatic gate decision, since the gate cannot mechanically
verify a redaction is complete. NEVER a raw environment dump. It does NOT re-author the secrets/paths
list — it reuses the project publication-safety rule by reference and enforces it as a HARD
packaging-fail. The manifest is ALSO the post-incident provenance record (an operator reconstructing a
misbehaving released run depends on it). EXCEPTION: a throwaway / local-only run that produces NO durable
artifact need not emit; but any run whose output COULD be promoted, shared, or kept as a
golden/validation/release artifact MUST emit a manifest BEFORE promotion (no retroactive manifest
fabrication); a genuinely-unavailable field is recorded as explicitly-absent, not omitted silently. OWNER:
the packaging/release owner (run provenance) + the publication-safety owner (the allowlist trust boundary
+ the dual value-scan + the HARD fail — the security-engineer slice's facet). PROBE: each
golden/validation/release artifact carries a full-field manifest, diffed at packaging — a pinned-dep
change without a re-baseline decision FAILS; layer-1 fails on a non-allowlisted key; layer-2 runs both
detectors and fails (or verified-redacts) on a machine-local path or credential value. [spine:
Determinism and ambient-input control, Publication safety, Sensitive-data handling and redaction,
Dependency introduction discipline] (broader than C1)

**D4 — Resource lifetime and mutable process-global state are composition-root-owned.** Every RESOURCE —
handle, connection, buffer, lock, subscription, transaction, precomputed/cached state, cancellation
token, temporary file, acquired external state — has an EXPLICIT owner (the composition root or an
explicitly-scoped object) and is cleaned up on every exit path per [spine: Resource lifecycle hygiene]
(success/failure/cancellation/timeout — judgment-bound: read the code and trace the cancellation and
timeout paths, do not assume one `finally`/`defer` covers them). A reusable-module LEAF holds NO mutable
process-global state; the only program-lifetime globals are CONST (the compile-bound registries /
shared-constant owners of C1) or DOCUMENTED once-only immutables (set once before use, never mutated
after; a LAZILY-initialized once-only immutable must be safely PUBLISHED before any concurrent reader —
eager init at the composition root, or a one-time synchronization primitive — an unsynchronized lazy
global is a data race). Every pointer/handle-bearing contract STATES its ownership and free rules (who
allocates, who frees, transfer vs borrow, nullability). The three net-new deltas over the spine cleanup
rule are: OWNERSHIP PLACEMENT (lifetime is the composition root's, tied to the same layering authority as
A1/A6), the no-mutable-leaf-global probe, and the documented-free-rules obligation. EXCEPTION:
deterministic automatic scoping (RAII / `defer` / `using` / context managers) covers the SUCCESS and
FAILURE paths for in-scope resources — accept it; but tracing GARBAGE COLLECTION reclaims MEMORY only
(not external handles, locks, or connections) and reaches nothing on cancellation or timeout, so any
EXTERNAL resource still needs an explicit owner with cleanup on failure/cancellation/timeout (a detached
or timed-out external handle is on no stack frame and no GC root, so neither unwind nor finalization
reaches it). OWNER: the composition root / explicitly-scoped object (lifetime + process-global state).
PROBE: no mutable process-global (non-const file-scope/static/module-level) state in a leaf (lint,
allowlisting const registries + documented immutables); every handle contract documents ownership/free;
cleanup-path coverage is judgment-bound (reviewer traces cancel + timeout paths). [spine: Resource
lifecycle hygiene, Determinism and ambient-input control] (adds ownership placement +
no-mutable-leaf-global on top of the spine cleanup rule)

**D5 — Parallel regions own their data per datum and merge deterministically.** Any mutable state CROSSING
a parallel boundary (a parallel-for/parallel-reduce, a thread/task pool, a parallel handler bind) —
measured or not — is exactly one of: WORKER-OWNED (thread/task-local), IMMUTABLE (read-only shared input),
ATOMIC-SUMMARY (an EXACTLY-associative, order-independent reduction over an INTEGER or BITWISE domain —
integer add; bitwise and/or/xor; integer min/max — a floating-point accumulator is NOT exactly
associative, and FP min/max carry NaN/signed-zero edge cases, so an FP reduction is a merge-owner datum,
not an atomic-summary), or REDUCED by a MERGE-OWNER in a CANONICAL merge order that is a C1-OWNED
invariant, not a per-region free choice (a fixed, order-deterministic combine, not whichever-finishes-
first). A non-associative reduction reordered across workers does not merely vary nondeterministically —
it produces a DIFFERENT numeric result, so the merge order MUST be the C1-owned canonical order (this is
the parallel reading of B2's "an order-sensitive reduction can change results — see C1"). Shared mutable
state is NEVER clobbered by concurrent workers, and NEVER guarded by a SERIALIZING LOCK on a measured/hot
parallel loop — a lock there is BOTH a performance hazard (serializes the region) AND a determinism
hazard (nondeterministic acquisition order changes an order-sensitive accumulation). A new parallel
region DECLARES, PER DATUM, its class (immutable / worker-owned / atomic-summary / merge-owner); the
per-datum requirement is load-bearing — one region may mix all four. EXCEPTION: an embarrassingly-parallel
region with no shared mutable state; a genuinely exactly-associative atomic summary; or a coarse
low-contention lock OFF the measured path guarding an ORDER-INSENSITIVE update on already-classified data
(the 4-class classification is universal; only the LOCK BAN is measured-loop-specific; an order-sensitive
accumulation under a lock stays a determinism hazard even off the hot path — route it through the
C1-canonical merge instead). OWNER: the parallel region's author (per-datum ownership) + C1 (the canonical
merge order). PROBE: each datum crossing a parallel boundary is classified; no shared mutable state
(process-global OR heap/captured) is written by concurrent workers outside its declared class — the
per-datum classification is UNIVERSAL and unconditional (every region declares it); any mutable state
reachable across the parallel boundary with NO declared class FAILS (fail-closed default); and no
lock/mutex is acquired inside a parallel region the author classifies hot — where a region counts as
reviewer-verified hot when EITHER (a) a repo-defined performance-critical marker tags it OR (b) a
profiling measurement PRESERVED at the repo-standard performance-evidence location (a repo-local
policy/checklist names the concrete path) and CITED in the commit/PR shows it on a measured-critical path
— an unarchived verbal claim is insufficient; ABSENT both (a) and (b), the lock-ban applies FAIL-CLOSED
to every parallel region as a candidate — opting OUT of the lock-ban requires (a) or (b) as positive
evidence (FAIL). [spine: Determinism and ambient-input control] (sharpens B2 toward the parallel case;
specializes D4)

## Protected properties (must not regress)

A structural change must preserve these invariants — each has a named owner and an enforcement probe;
a regression in any is a blocking finding:

- **Acyclic, downward-only dependency graph** (A1) — probe: the repo-standard build / lint /
  import-graph / CI gate.
- **No lower-layer ambient reads** (C2) — probe: `grep getenv` / cmdline in lower modules returns no
  undocumented hit.
- **One owner per cross-cutting invariant** (C1) — probe: START from an in-scope decision or
  invariant, never from syntax. Name the policy owner who would legitimately change the value, the
  change that would trigger it, the consumers or boundary representations that MUST co-vary, and the
  one place they would look; ONLY then grep for definitions and read sites — one definition, others
  call it. A world fact, protocol constant, or algorithm-local literal fails the trigger or the
  co-variation test and is excluded (that exemption is deliberate; a literal is a discovery seed,
  never a finding). Without co-variation it is not C1 at all — a lone hardcoded policy value may
  still breach anti-hardcoding, and keeping those classes apart is what stops this probe becoming a
  literal hunt. Aim it at VALUES explicitly, not only at predicates and orderings: a real audit ran
  this lens, found "one conceptual decision has four independent owners", and never asked who owns
  the number — the letter below already said "a shared constant … a calibration table" and was not
  applied.
- **No untracked duplicate representations** (A7, C1) — probe: duplicates only behind a codegen source
  or a drift gate.
- **Entry points hold no second-consumer decision** (A5) — probe: each decision in an app/tool has no
  twin a second entry point would need.
- **Test support deletes cleanly** (C4) — probe: removing an implementation edits no other tests.
- **No leaf process-termination** (D1) — probe: termination-primitive grep over the repo-defined
  reusable-module boundary (where none is declared: the non-entry-point/non-test tree, review-bound); NEW
  hit in the change FAILS; existing baseline a frozen debt.
- **Diagnostics through one injected port with registered IDs** (D2) — probe: no ad-hoc sink/env-read
  outside the support owner; every ID resolves; disabled-path residue check is STRUCTURAL-LINK FIRST
  (owner absent from the measured unit's link/import/macro-expansion set, or disabled path a build-time
  constant — checkable from the build/link graph), release-build asm/IR ONLY where the perf budget demands
  the zero-residue proof; review-bound on interpreted/JIT.
- **Every result artifact carries a publication-safe full-field manifest** (D3) — probe: packaging
  emits+diffs the manifest (toolchain/flags, pinned deps, platform identity, determinism/FP mode, seed,
  parallel config + reduction partitioning, input hashes, config snapshot, contract/schema versions,
  strategy/algorithm); a missing field FAILS; layer-1 allowlist + layer-2 two-detector value-scan
  fail/verified-redact on machine-local path / credential.
- **No mutable process-global in a leaf; cleanup on all exit paths** (D4) — probe: no-mutable-global lint;
  handle contracts document free rules; cleanup-path coverage judgment-bound (cancel + timeout traced).
- **Parallel data owned + deterministic C1-canonical merge** (D5) — probe: per-datum classification; no
  shared-mutable clobber by concurrent workers; no lock on a (reviewer-verified) hot parallel loop.
- **No stale-relation residue after a superseding change** (C6) — probe: post-change grep for the old name
  + stale-relation phrases returns only LIVE relations (discrimination review-bound).
- **No general owner edited to add a single concrete instance** (M) — probe: the extension-churn budget
  (mechanical for under-abstraction); over-abstraction / right-level is review-bound.

## Falsifiable checklist (every structural change passes; a NO is a blocking finding)

Each item NAMES the single owner and the ENFORCEMENT PROBE (the grep / build / lint / validator / CI
check that catches a violation):

- [ ] New capability lands in its single owning module; no second copy (grep the symbol/operation, not
      the name).
- [ ] Every dependency edge points strictly down the graph or to an interface leaf; no edge into a
      sibling's private/internal module across a band; no upward or cyclic edge — caught by the
      repo-standard build/lint/import-graph/validator/CI gate (A1).
- [ ] No generic engine include/symbol/edge names a specific consumer/feature/method (A3).
- [ ] No entry-point unit holds a decision a second entry point would also need (A5).
- [ ] Any capability defined in ≥2 places where the lowest core could be reused is decomposed: core
      reused, only glue per-consumer (A7) — no copy-to-dodge-a-dependency.
- [ ] A new scenario was added by editing an adapter/composition/interface, NOT by a scenario-specific
      backend edit (A2/C3); a backend edit, if any, generalized a missing capability and protected
      existing consumers.
- [ ] No lower module reads env/CLI/global scenario policy; config is parsed once at the top and
      injected down (C2) — `grep getenv`/cmdline in lower modules adds no hit unless documented
      diagnostic-only, support-owned, with no business/semantic/output/security/control-flow effect.
- [ ] Every cross-cutting invariant/predicate/constant has one owner all consumers call; none is
      re-defined or re-typed "to stay consistent" except a hard-boundary representation derived from
      one source or guarded by a drift gate (C1).
- [ ] Any hot-path seam collapse FOR SPEED cites a profile measurement and keeps one coherent owner
      (B1); no seam splits a measured-critical/order-sensitive sequence (B2). (This item is
      judgment-bound — it asks whether the cited measurement is adequate.)
- [ ] Generic test support is under a test-only tree, parameterized over a contract, not homed in one
      implementation (C4); each implementation deletes with zero edits to other tests.
- [ ] A new feature could be added as plugin + thin scenario without a new parallel silo (A4).
- [ ] Accepted debt is a tracked grandfathering entry (owner/scope/expiry/no-expansion), not a silent
      re-bless or a license for new violations (C5).
- [ ] No reusable module terminates the process; failure is a typed RETURNED value (severity+id+cause);
      the composition root owns termination + the recovery decision (D1).
- [ ] Diagnostics route through one injected support-owned port (coarse-threaded); IDs resolve in the
      const registry (versioned contract); disabled-path residue check is structural-link-first (owner
      absent from the measured unit's link/import/macro-expansion set, or build-time constant), asm/IR only
      on perf-budget demand, review-bound on JIT (D2).
- [ ] Every result/golden/validation/release artifact carries a publication-safe, allowlist-built run
      manifest — toolchain/flags, pinned deps, platform identity, determinism/FP mode, seed, parallel
      config, input hashes, config snapshot, contract/schema versions, strategy/algorithm;
      missing/divergent/incomplete fails packaging (D3).
- [ ] No mutable process-global state in a leaf (only const registries / documented safely-published
      immutables); every resource has an owner with cleanup on all exit paths (judgment-bound: cancel +
      timeout); handle contracts document free rules (D4).
- [ ] Mutable state crossing a parallel boundary is classified per datum (immutable / worker-owned /
      exactly-associative-integer/bitwise-atomic-summary / merge-owner) and merged in the C1-canonical
      order; no shared-mutable clobber; no serializing lock on a parallel loop — verified-hot by (a) a
      perf-marker or (b) a preserved profiling artifact; absent both, the lock-ban applies fail-closed to
      all parallel regions (D5).
- [ ] A superseding change left ONLY the correct current state; the old name + stale-relation phrases were
      grepped and erased, keeping only LIVE relations (C6) — the stale-vs-live discrimination is
      review-bound (grep surfaces candidates; a reviewer verifies each before erasing).
- [ ] No general owner was edited to add a single concrete instance (M) — churn is mechanical; the
      over-abstraction / right-abstraction-level judgment is a reviewer verdict, not a grep.
- [ ] Every binding doc/rule reference resolves to an existing in-tree artifact (no folklore refs).

## Terms and Abbreviations

- **layer / module** — a single-abstraction-level unit with a narrow interface and one owner.
- **silo** — a feature implemented as a big independent program with private copies of shared layers
  (the anti-pattern).
- **core / glue (A7)** — the lowest pure single-owner unit (reused, never re-typed) vs the
  per-consumer orchestration over it.
- **dependency inversion (A6)** — contract defined on a stable surface both sides may depend on,
  implementation injected from above.
- **interface leaf** — an interface / protocol / contract module with no downward dependency edges,
  safe to depend on across layers.
- **adapter / binding / composition (A2)** — the thin edit surface where new scenarios are wired, on
  top of stable backends.
- **dependency graph / DAG** — the directed graph of module dependencies (imports / requires / link
  edges); must be acyclic with edges pointing down.
- **cross-cutting invariant (C1)** — a value or rule that must stay identical across many modules (a
  mode predicate, a canonical order, a shared constant) and therefore needs exactly one owner.
- **upward control-flow leak (C2)** — a lower module reading ambient policy (env / CLI / global mode)
  that should have been injected from above, even when no dependency edge exists.
- **hard boundary** — a process / language / ABI / generated-code / DB-schema / external-protocol
  boundary across which a derived-from-one-source or drift-gated duplicate representation is tolerated.
- **composition root / outer ring** — the app/entry layer that owns process termination + the recovery
  decision (D1) and resource/global lifetime (D4).
- **diagnostic port (D2)** — the single support-owned, injected, coarse-threaded channel all diagnostics
  flow through.
- **event-ID registry / versioned diagnostic IDs (D2)** — the const registry of stable diagnostic event
  IDs tooling depends on as an API contract.
- **run manifest / run provenance (D3)** — the machine-readable record of everything needed to reproduce
  a run (toolchain, pinned deps, platform identity, determinism/FP mode, seed, parallel config, input
  hashes, contract/schema versions, strategy/algorithm).
- **pinned dependency (D3)** — an exact version/hash, never a moving tag/branch/`latest`.
- **allowlist-built snapshot (D3)** — a config/env capture that is default-closed (only listed keys) with
  a two-detector value-scan backstop, never a raw dump.
- **worker-owned / atomic-summary / merge-owner (D5)** — the per-datum classes for state crossing a
  parallel boundary; atomic-summary is exactly-associative integer/bitwise only; the merge order is the
  C1-owned canonical order.
- **abstraction-level meta-law (M)** — abstract by default, concretize only at the leaf that needs it; an
  owner edit forced by a new instance is the violation.
- **over-abstraction (M)** — a one-instance indirection layer with no churn justification; the opposite
  failure to under-abstraction.
- **stale relation vs live relation (C6)** — a stale relation asserts an obsolete relationship (erase); a
  live relation asserts a current fact (keep).
- **stale-relation residue (C6)** — a name/alias/comment/registry entry/pointer in the live tree that
  still asserts an obsolete relationship after a superseding change (the thing C6 erases).
