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
payoff is three properties, which organize the rest of this file:

- **Generalization / scaling** — new cases land as thin compositions, so the system scales to new
  scenarios without forking the stack.
- **Performance** — boundaries are stable and collapsed only under measurement, so abstraction never
  silently costs speed and optimization stays safe.
- **Stability / reproducibility** — single ownership of capabilities and cross-cutting invariants
  means a change stays in its blast radius and results stay consistent.

These SHARPEN, not replace, the always-on spine rules. The spine rule each one extends is tagged
inline as `[spine: <rule>]`; an item with no tag is net-new.

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
exception: see C1.) [spine: No logic duplication, Reuse before hand-rolling]

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
this single ownership. [spine: No logic duplication]

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

## Protected properties (must not regress)

A structural change must preserve these invariants — each has a named owner and an enforcement probe;
a regression in any is a blocking finding:

- **Acyclic, downward-only dependency graph** (A1) — probe: the repo-standard build / lint /
  import-graph / CI gate.
- **No lower-layer ambient reads** (C2) — probe: `grep getenv` / cmdline in lower modules returns no
  undocumented hit.
- **One owner per cross-cutting invariant** (C1) — probe: grep the operation/constant; one definition,
  others call it.
- **No untracked duplicate representations** (A7, C1) — probe: duplicates only behind a codegen source
  or a drift gate.
- **Entry points hold no second-consumer decision** (A5) — probe: each decision in an app/tool has no
  twin a second entry point would need.
- **Test support deletes cleanly** (C4) — probe: removing an implementation edits no other tests.

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
