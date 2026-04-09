# Skill-Pack Maintenance

Internal rules for maintaining the Claudestrator skill pack. Not installed into target repositories.

## Maintenance roles

- `$lead`: coordinate maintenance work, routing, accepted artifacts, and gate decisions
- `$knowledge-archivist`: docs, references, structure, canonical-source alignment, reports, and hygiene cleanup
- `$toolchain-engineer`: build, packaging, installation, reproducibility, and developer ergonomics for the skill pack
- `$qa-engineer`: verification of maintenance changes against accepted behavior and likely regressions
- `$architecture-reviewer`: maintainability and cohesion gate for structural or semantic control-plane changes to the pack
- `$external-worker`: cross-provider implementation adapter for eligible implementer roles
- `$external-reviewer`: cross-provider review and QA adapter for eligible reviewer-side roles
- `$consultant`: optional independent second opinion for ambiguous workflow or policy changes
- `$product-manager`: roadmap, sequencing, and admission decisions for the skill pack itself

## Maintenance rules

- Keep `src.claude/CLAUDE.md` as the repo-level governance source
- Changes to shared governance rules (delegation, gate semantics, REVISE cap, re-intake, task memory) must be propagated to `lead.md` in the same commit; `operating-model.md` is a reference only and should stay aligned
- Update `src.claude/agents/<role>.md` when trigger or prompt behavior changes
- Update `src.claude/agents/contracts/operating-model.md` when orchestration or gate semantics change
- Update `src.claude/agents/contracts/external-dispatch.md` when consultant-mode schema, provider paths, provenance rules, or external adapter semantics change
- Update `src.claude/agents/consultant.md` when consultant execution policy changes, keeping it aligned with the shared external-dispatch contract instead of duplicating dispatch rules inline
- Use `$knowledge-archivist` for repository hygiene, canonical-source alignment, documentation upkeep, and reference maintenance
- Route semantic repository control-plane changes prepared by `$knowledge-archivist` through an independent `$architecture-reviewer` gate before completion or publication; hygiene-only edits such as link fixes, formatting, index sync, archive moves, and non-semantic wording cleanup do not require that extra reviewer

## Policy boundaries

Use the global layer (CLAUDE.md) only for rules that frequently prevent expensive mistakes, apply in most repositories, stay short and testable, and do not duplicate specialist lanes.

### Keep global (CLAUDE.md)

- delegation and fact-first flow
- change isolation, logic discipline, and verification discipline
- security, performance/resource, maintainability, environment/reproducibility, and dependency baselines

### Keep repo-local

- compatibility and deprecation policy
- API, config, schema, and migration evolution rules
- rollback expectations, rollout rules, and project-specific budgets or SLAs
- allowed toolchains, shells, build systems, concrete build/test commands, canonical paths, and source-of-truth references
- repository-specific portability assumptions

### Keep in specialist workflows

- threat modeling and trust-boundary analysis
- profiling methodology and bottleneck analysis
- architecture verdicts and major design tradeoffs
- persisted-state evolution and observability, SLO, or operability requirements
- domain-specific algorithmic, numerical, UX, accessibility, security, and performance review heuristics

### Do not force into global

- long catalogs of design principles without an operational check
- academic reminders without a concrete decision test
- tool-specific safety rules already enforced elsewhere
- vague slogans such as `KISS`, `YAGNI`, or `clean code` without a falsifiable use rule
