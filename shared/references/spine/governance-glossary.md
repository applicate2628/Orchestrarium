# Shared governance glossary

Terms, abbreviations, role names, status labels, and provider names used across the shared governance spine (`shared/AGENTS.shared.md` → installed `AGENTS.md`) and its references. A glossary is reference material by definition — it is read on demand, not loaded into every session — so it lives here rather than in the always-loaded spine.

- `ADR`: Architecture Decision Record; a durable document recording an architecture decision and its context.
- `quick-fix`: the execution-first route used only when the shared admission predicate is fully satisfied; any failed predicate requires re-classification.
- `AGENTS.md`: repository or install-level governance file read by agent runtimes that support this convention; in this repo it is the installed copy of the shared spine.
- `API`: Application Programming Interface; an externally observable interface exposed by code or services.
- `artifact`: a concrete output such as a brief, research memo, design, plan, patch, review, report, or closure note.
- `ASSUMPTION (UNVERIFIED)`: the required label for any decision-driving claim that has not been verified by one of the four evidence categories.
- `BLOCKED`: workflow state reserved for a real external blocker, unavailable prerequisite, or missing required decision.
- `build-vs-buy gate`: the decision point where an implementation chooses between existing mechanisms and a new custom implementation.
- `CAD`: Computer-Aided Design; software and file formats used for technical drawings, geometry, or engineered layouts.
- `CI`: Continuous Integration; automated checks run by a build or repository service.
- `CLI`: Command-Line Interface; a tool invoked from a shell or terminal.
- `correlation ID`: an identifier used to connect logs, events, requests, and state changes that belong to one user action or workflow.
- `data point`: one concrete observed value, log line, field, return code, screenshot fact, or command result used as evidence.
- `gate`: an acceptance point that must verify an artifact before work advances.
- `general case`: the full class of behavior governed by the same requirement, cause, owner, or invariant.
- `concept/abstraction level`: the level of behavior being changed, from one visible symptom up through the owner-level invariant that explains all sibling cases.
- `hash`: a deterministic digest of file bytes or content; useful for identity checks but not visual verification.
- `hand-roll`: implement custom logic from scratch instead of using an existing repo mechanism, framework feature, installed dependency, or mature optimized library/tool.
- `invariant`: a rule that must remain true across all relevant states.
- `kostyl`: a workaround or crutch that hides a symptom without correcting the root-cause logic; allowed only as an explicitly-labeled `WORKAROUND`.
- `KISS`: named only as an example of a vague slogan that needs an operational rule before becoming governance.
- `local special case`: an implementation that handles one visible example while leaving the owner-level class undefined or inconsistent.
- `Markdown`: a lightweight markup format used for repository documentation.
- `mature optimized library/tool`: a maintained external solution with enough adoption, documentation, versioning, compatibility evidence, and fit for the task's correctness/performance constraints.
- `MCP`: Model Context Protocol; a tool/server protocol used by some agent runtimes.
- `metadata`: descriptive file or runtime information such as dimensions, timestamps, MIME type, or generator fields.
- `MIME`: Multipurpose Internet Mail Extensions; a standard content-type label family used to describe file or payload formats.
- `PASS`: workflow state meaning a scoped artifact has passed the relevant gate.
- `provenance triad`: for a computed-results table, the (1) formula/model/procedure, (2) code/script path, and (3) input artifacts that together let the values be reproduced and audited.
- `provider`: an execution backend or model family such as Codex, Claude, Gemini, or Qwen.
- `pub/sub`: publish/subscribe messaging; a pattern where publishers emit events and subscribers receive them through a shared channel.
- `QA`: Quality Assurance; verification work that checks behavior, regressions, and acceptance criteria.
- `REVISE`: workflow state meaning an artifact must return to the same role for bounded correction.
- `SLA`: Service-Level Agreement; an external reliability or performance commitment.
- `SLO`: Service-Level Objective; an internal reliability or performance target.
- `spine`: the always-loaded `AGENTS.shared.md` content; carries the binding operational form of every rule, with elaboration in `shared/references/`.
- `SSE`: Server-Sent Events; an HTTP-based stream used by servers to push events to clients.
- `TeX`: a typesetting system and math-notation language used by many Markdown math renderers.
- `UI`: User Interface; the user-facing interaction surface.
- `UX`: User Experience; usability, flow, comprehension, and interaction quality.
- `visual artifact`: an image, diagram, drawing, render, chart, plot, screenshot, CAD/exported drawing, or similar visible output.
- `WORKAROUND`: the required commit label for a kostyl, disclosing the named-but-unfixed root cause, scope, and lifetime.
- `YAGNI`: named only as an example of a vague slogan that needs an operational rule before becoming governance.

## Engineering-hygiene working definitions

- `owning boundary`: the module, interface, or approved extension seam responsible for a behavior or invariant.
- `owner`: the module, state machine, contract, lifecycle, or pipeline boundary responsible for maintaining an invariant.
- `external contract`: any promise observable outside that boundary, including APIs, configs, schemas, file formats, persisted-state expectations, events, or CLI surfaces.
- `repo-standard checks`: validation commands, tests, lint, typecheck, build, publication scan, or review checklist the repository defines.
- `repo-standard mechanism`: an existing repository-owned helper, subsystem, framework convention, dependency, or script that already owns the relevant capability.
- `runtime speed`: application execution speed, latency, throughput, or responsiveness; a performance constraint, not development speed.
- `stack choice`: the selection of repository mechanism, framework feature, dependency, library/tool, service, or custom implementation used to deliver a capability.
- `smallest safe reversible subset`: the narrowest change that moves work forward without locking in unresolved policy, architecture, or behavior.
- `ambient input`: hidden runtime influence such as wall clock, locale, timezone, filesystem ordering, process-global state, ambient env vars, or uncontrolled randomness.
