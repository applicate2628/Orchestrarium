# Causal UI Continuity

This reference is the sole normative source for Orchestrarium's platform-neutral
continuity contract for dynamic user-interface transitions. It governs the
observable result of a transition, not a framework application programming
interface (API) or rendering technique. The Russian file at
`ru/ui-transition-continuity.md` is a required non-authoritative operator mirror.

## Normative invariant

For every transition from an authoritative settled state `S0` to an
authoritative settled state `S1`, a continuity dimension may change only when an
observed authoritative input delta or explicit user intent positively permits
that dimension to change, and only inside the declared causal scope. Every other
applicable dimension and still-valid task state remains stable.

Permission is declared before the post-state is evaluated. Labels such as
"responsive", "refresh", "accessibility", or "loading" cannot retrospectively
legalize an unexplained delta. When task-relevant inputs are unchanged, repeated
settled refreshes are idempotent on every applicable dimension. This rule is not
a universal pixel freeze: adaptive, structural, corrective, lifecycle, and
explicitly intentional changes remain possible within their declared bounds.
In plain terms: this is not a universal pixel freeze.

Framework mechanisms such as showing or hiding an element, changing a size
hint, resetting a model, replacing a render object, or starting an animation are
neither banned nor approved by name. Their observed transitions pass or fail the
same causal contract.

## Transition classes

| Class | Authoritative cause | Positively permitted change | Still preserved |
| --- | --- | --- | --- |
| `exact-replay` | No task-relevant input delta. | None after settlement. | All applicable dimensions. |
| `value-status` | Scalar value, progress, status, or truthful content changes without a structural, environment, or intent change. | Content and announcement semantics; local geometry only under the expected-variability rule. | Entity structure and order, valid task state, unrelated geometry, focus, and viewport. |
| `structural` | Membership, meaningful order, hierarchy, grouping, available actions, or entity validity changes. | Causally affected membership, order, layout, visibility, and invalidation. | Identity and valid state for surviving entities; declared fallback for removed targets. |
| `adaptive` | Viewport, breakpoint, orientation, density, zoom, font scale or metrics, localization, direction, text spacing, assistive presentation, or motion preference changes. | Necessary reflow, metrics, reading order, affected geometry, or motion substitution. | Information, operability, semantic identity, valid focus or selection, and recognizable task anchors. |
| `intentional` | An explicit user command with a declared observable effect. | Only the named layout, navigation, visibility, ordering, density, zoom, or expansion effects. | Every unrelated dimension; temporal proximity alone is not intent. |
| `corrective` | Correctness, safety, security, authorization, or validity invalidates prior state. | Narrow invalidation of unsafe, unauthorized, removed, or misleading objects or actions. | Unaffected objects and state; predictable focus recovery and truthful explanation. |
| `lifecycle` | Virtualization or platform lifecycle legitimately recreates presentation objects. | Render-instance replacement. | Semantic identity and every still-valid task-state dimension before settlement. |

One transition may carry more than one cause, but every changed dimension needs
its own positive permission. A viewport change can permit reflow without
permitting selection loss; removal of one entity can permit its invalidation
without permitting unrelated focus movement.

## Expected variability and bounded adaptation

Predictable bounded variation is budgeted before the first stable frame:

- counters with known ranges, progress labels, busy or idle indicators, status
  icons, and control-state variants reserve the maximum required capacity or use
  a stable overlay;
- enabled, disabled, and loading states update the existing semantic control in
  place when its identity is unchanged;
- reserved capacity remains operable at supported zoom, font scale, text
  spacing, and localization settings.

Unbounded content, including user data, localization, accessibility scaling,
dynamic type, and genuinely changed structure, must not be clipped merely to
preserve coordinates. It may reflow inside its declared causal scope while
unrelated dimensions and task anchors remain stable. Accessibility,
localization, responsive, structural, lifecycle, corrective, and explicit-user-
intent changes are positively bounded permissions, not a blanket exemption.

## Continuity dimensions

| Dimension | Default observation | Preservation rule |
| --- | --- | --- |
| `spatial` | Logical rectangles, relative anchors and order, overlap, viewport attachment, and container, header, list, row, and control sizes. | No meaningful delta outside permitted causal scope; tolerance covers deterministic quantization only. |
| `semantic-object` | Stable application or entity key and surviving membership. | Surviving entities retain identity; keys never silently alias different entities. |
| `model` | Membership, meaningful order, hierarchy, grouping, and available actions. | The model matches the transition class; value-only refresh does not churn structure. |
| `render-object` | Widget, component, view-holder, or render-node incarnation. | Recreation is diagnostic, not automatically a defect; state-bearing recreation restores higher-level state. |
| `interaction` | Focus, selection/current, scroll or viewport anchor, expansion, and edit or input state. | Every still-valid state stays attached to the same semantic entity or declared task anchor. |
| `item-metric` | Row or item height and width plus their measurement inputs. | Metrics remain stable when measurement inputs are unchanged; adaptive or content causes alter only affected metrics. |
| `accessibility/status` | Focus meaning and visibility, semantic ordering, and status announcement. | Required status remains programmatically exposed; ordinary status updates do not steal focus. |
| `motion` | Animation or transition state and reduced-motion preference. | Refresh creates no motion without permission; meaning and correspondence never depend on motion alone. |

The observation scope includes all already-visible structural and interactive
descendants of the affected surface plus off-screen semantic anchors required
to preserve selection/current and scroll. Virtualized objects are compared by
semantic identity, not by requiring each presentation object to persist.

Invalid or removed state is not preserved blindly. The transition declares its
invalidation reason and deterministic fallback, such as the nearest surviving
entity, owning container, invoking control, or application-defined safe target.

## Atomic transition and settled semantics

A transition is one correlated semantic transaction:

1. The transition authority records the cause vector, positive permission
   vector, observation scope, and revision.
2. The canonical update path changes the model or content.
3. The one writer for each mutable dimension commits the same revision.
4. Valid focus, selection/current, scroll anchor, expansion, input,
   accessibility publication, and motion policy are restored or deliberately
   invalidated through the declared fallback.
5. One downstream-observable aggregate settled observation becomes available.

`continuity-settled` names the evidence seam; it does not mandate a new
application event. A platform adapter may bind an existing public commit,
layout, frame, or test signal only when it proves that all applicable owners
have committed the same revision and no later same-revision mutation remains.
Settledness is revision-correlated. A fixed sleep or one observation that an
event loop became idle is insufficient. A missing owner, duplicate writer, or
missing aggregate settled evidence fails closed.

Every user-perceivable loading, pending, error, permission, skeleton, or
progressive-render phase is a separate transition with its own cause,
permissions, announcement, and settled observation. Equal endpoints do not hide
an intermediate discontinuity or partial commit.

## Portable transition record

Only non-default or structurally meaningful transitions need an explicit
record. The portable schema is:

`{ surface, revision, transition class, authoritative cause, semantic keys, applicable dimensions, single writer per mutable dimension, permitted effects, preserved anchors, invalidation fallback, observation adapter, settled evidence }`

`exact-replay` and ordinary `value-status` refreshes inherit the closed default:
preserve every applicable dimension except causally changed content and required
announcement semantics. They do not require repetitive per-refresh prose.

## Portable deterministic oracle

Named guard: `UIContinuity/causal-transition-matrix`.

For every scenario:

1. Reach an authoritative initial settled state.
2. Capture controlled input fingerprints and observations for every applicable
   dimension.
3. Apply one transition through the canonical update path.
4. Await the revision-correlated authoritative settled observation, never a
   fixed sleep.
5. Compare each observed delta with the predeclared cause, positive permission,
   causal scope, preservation rule, and fallback.
6. Starting from one baseline, perform three post-baseline equivalent refreshes
   and require identical verdicts and observations within a predeclared
   deterministic quantization tolerance.
7. Plant at least one unpermitted delta and require the oracle to reject it.
8. Run positive structural, adaptive, intentional, and corrective cases and
   require only their declared dimensions to change.

The three repetitions are a portable deterministic smoke-test floor, not
statistical proof. A project may declare a larger deterministic corpus before
execution. Screenshots, video, or web Cumulative Layout Shift may supplement
the trace but cannot be the sole evidence because they do not fully observe
identity, size-only changes, focus, selection, scroll, announcements, or motion.

## Required metamorphic scenarios

| Scenario ID | Positive case | Negative control or preservation requirement |
| --- | --- | --- |
| `exact-replay` | No dimension changes after settlement. | Move or resize a task object, alter an item metric, or recreate a state-bearing object without restoration: reject. |
| `value-status-progress` | Content and status announcement may change; bounded reserved-slot content does not relayout. | Unrelated geometry, focus, selection/current, or viewport movement: reject. |
| `structure-change` | Affected membership, order, layout, and invalid removed target may change. | Surviving identity and valid state remain; remove one surviving anchor: reject. |
| `responsive-adaptation` | Breakpoint, orientation, or viewport changes may alter affected geometry, grouping, and metrics. | Preserve identity, information, operability, valid focus and selection, and a recognizable task anchor. |
| `font-locale-adaptation` | Font scale, text spacing, locale, or direction may cause necessary wrapping, reflow, metrics, and reading-order changes. | Clipping content to retain old geometry is forbidden; unrelated controls need a declared dependency edge to move. |
| `interaction-anchor` | An invalid target may use its declared deterministic fallback. | With valid targets, focus, selection/current, scroll anchor, expansion, and input state remain on the same semantic entities. |
| `status-announcement` | A truthful programmatic status event may change. | Missing or duplicate announcement or focus theft: reject even when pixels match. |
| `explicit-layout-intent` | An explicit command may produce only its declared layout effects. | Nearby unrelated movement: reject; timing alone does not establish intent. |
| `corrective-invalidation` | An invalid target and its required fallback may change. | Clearing unrelated valid state: reject. |
| `lifecycle-recreation` | Lifecycle recreation may change a render incarnation. | Loss of semantic identity or valid task state before settlement: reject. |
| `reduced-motion` | Motion may be removed or replaced. | Final meaning, geometry, identity, focus, and state remain equivalent. |
| `premature-settlement` | No late mutation is permitted after aggregate settlement. | Engineer a late same-revision mutation and require the observation adapter to be rejected. |

## Executor routing

The canonical contract alone owns the scenario matrix, dimension schema,
verdict meanings, and failure identifiers. Platform executors bind observations
and run it; they do not copy or redefine it.

| Platform | Implementation seam | Independent executor |
| --- | --- | --- |
| Qt Widgets and Qt Quick/QML | The Qt implementation owner supplies the canonical update path and a proven settled adapter. | `$ui-test-engineer` executes the portable oracle through the repository's Qt harness. This role remains Qt-only. |
| web/React | `$frontend-engineer` supplies the canonical update path and settled adapter. | `$qa-engineer` executes through the repository's browser, component, or end-to-end harness. |
| native mobile | The admitted platform implementation owner supplies the canonical update path and settled adapter. | `$qa-engineer` executes through the repository's platform instrumentation or UI harness. |

A missing required harness is `BLOCKED` or `UNVERIFIED`; it is not permission to
broaden the Qt-only role, substitute screenshots, or omit the gate.
`$accessibility-reviewer` and `$ux-reviewer` remain independent outcome gates,
and `$architecture-reviewer` owns the bilingual semantic-parity verdict and
single-owner architecture review.

## Failure identifiers

| Failure ID | Meaning |
| --- | --- |
| `UI-CONTINUITY-INPUT-UNACCOUNTED` | Controlled authoritative inputs differ outside the declared cause vector. |
| `UI-CONTINUITY-OWNER-COLLISION` | More than one participant can independently commit one mutable dimension, or the aggregate settled seam has no single authority. |
| `UI-CONTINUITY-SETTLED-UNPROVEN` | A required owner has not committed, or a same-revision mutation occurs after settled evidence. |
| `UI-CONTINUITY-CAUSALITY-BREACH` | A changed dimension lacks positive permission or lies outside causal scope. |
| `UI-CONTINUITY-PARTIAL-COMMIT` | Visible dimensions or announcements expose different revisions in one claimed transition. |
| `UI-CONTINUITY-KEY-CONFLICT` | A surviving semantic key is missing or duplicated, or an incompatible entity is rebound to it. |
| `UI-CONTINUITY-STATE-LOSS` | Valid focus, selection/current, scroll anchor, expansion, or input state is lost. |
| `UI-CONTINUITY-INVALID-STATE` | State remains attached to an invalid, unsafe, unauthorized, or removed entity. |
| `UI-CONTINUITY-A11Y-MISMATCH` | Required status, focus, or motion semantics are absent, duplicated, or cause unpermitted focus movement. |
| `UI-CONTINUITY-ADAPTATION-BLOCKED` | Retaining old geometry clips content, obscures focus, loses information, or makes admitted adaptation inoperable. |
| `UI-CONTINUITY-NOT-SETTLED` | Layout or state oscillates, or authoritative settled evidence cannot be obtained. |
| `UI-CONTINUITY-TRANSIENT-UNOBSERVED` | Equal endpoints conceal a user-perceivable undeclared intermediate discontinuity. |
| `UI-CONTINUITY-CONTRACT-DRIFT` | The normative contract, installed neutral leaf, role pointer, or declared projection differs from its accepted source. |
| `UI-CONTINUITY-DOC-DRIFT` | Root documentation disagrees with the accepted neutral-leaf topology, targets, pointers, language authority, or exclusions. |
| `UI-CONTINUITY-RU-SEMANTIC-DRIFT` | The required Russian mirror changes or omits the operative meaning of a normative English row or section. |

Diagnostics use opaque semantic keys, logical geometry, state classifications,
revision identifiers, and registered event identifiers. They exclude raw user
text, credentials, accessible-content payloads, and production data unless
separately authorized.

## Ownership and distribution boundary

This English file is the only semantic authority. The Russian mirror translates
it and is reviewed atomically but has no runtime consumer. The production
installer projects only these English bytes into the neutral live-pack leaf
`contracts/ui-transition-continuity.md`; the full maintainer reference tree and
the Russian mirror are not installed. Roles point to that neutral leaf instead
of carrying provider or framework copies.

This contract creates no new workflow stage, no new hook, no new operator
command, no new dependency, and no documentation semantic owner. It does not
alter application UI code, choose framework APIs, or add a provider-specific
semantic copy. Root documentation is a topology projection only.

Named documentation guard: `UIContinuity/documentation-projection`. It returns
`UI-CONTINUITY-DOC-DRIFT` when the root documentation omits or misstates the
neutral leaf, one of the four live install targets, either role-relative pointer,
English/Russian authority, the full-tree exclusion, or the provider-copy
exclusion while source and installer topology remain unchanged.

## Terms and Abbreviations

- **API:** Application Programming Interface.
- **Authoritative input:** Trusted data, environment, validity, or explicit
  user-intent fact that may cause a transition.
- **Causal scope:** Objects and independent dimensions reachable from one
  declared authoritative cause.
- **Continuity dimension:** An independently observed category of UI state.
- **Metamorphic scenario:** A test relating controlled input changes to the
  exact output dimensions that may and may not change.
- **QML:** Qt Modeling Language, the declarative language used by Qt Quick.
- **Settled observation:** Evidence that all applicable owners committed one
  correlated revision and no later mutation of that revision remains.
- **UI:** User Interface.
- **UX:** User Experience.
