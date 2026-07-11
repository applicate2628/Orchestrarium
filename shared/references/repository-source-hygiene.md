# Repository Source Hygiene — Reference

This is a reference document for the source-tree organization rules `Directory-level entity separation` and `Trash hygiene and archival` defined in `shared/AGENTS.shared.md` `### Scope and ownership discipline`. It is **NOT** installed into target projects — it is a methodology reference plus repo-local concretization for this monorepo.

## Rules summary

Two rules govern source-tree hygiene:

1. **Directory-level entity separation** — every source directory has one primary entity type and ownership/lifecycle contract; the directory's purpose must be expressible in one sentence; new files placed by classifying owner/lifecycle + I/O contract.
2. **Trash hygiene and archival** — delete or archive obsolete files within the admitted change surface, subject to `Worktree safety`; archival path with breadcrumb when deletion loses recoverable history.

## What counts as an "entity type"

An entity type is the **kind of work the file does**, classified by:

- **Actor or lifecycle that owns or invokes it.** Runtime hook (PreToolUse/Stop, called by Claude/Codex CLI); agent-side wrapper (called by agent during session via tool); installer (called by maintainer during `--global` install); validator (called by CI or maintainer); gate (deny-on-fail check before publication action); skill/command (called by agent via Skill or slash-command); runtime helper (called by user or scripts in target projects after install).

- **Input/output contract or side effects.** What the file consumes (stdin envelope / argv / config file / file-system state) and produces (structured-deny JSON / exit code / written file / git ref / log entry). Two files with the same contract are the same entity type; two files with different contracts are not.

Platform variants (`.sh`/`.ps1`/`.py`) of the same command with the same contract count as **one entity**, not multiple.

## This repo's grandfathered exceptions

`shared/AGENTS.shared.md` `Directory-level entity separation` requires directories to organize around one primary entity type. The Orchestrarium monorepo has **three deliberately co-located directories** that serve a documented design constraint and are exempt from the per-entity-type split:

- `src.claude/agents/scripts/` — Claude pack: co-locates blocking-enforcement hooks (`check-bugfix-discipline.*`, `check-git-push-gate.*`, `check-passive-polling-stop.*`, `check-work-items-archival-stop.*`, plus the shared `hook_common.py`), SessionStart context hooks (`mcp-usage-reminder.*`, `agents-mode-reminder.*`), provider invocation wrappers (`invoke-claude-api.*`, `invoke-claude-prompt.*`, `invoke-codex-prompt.*`), publication gates (`check-publication-safety.*`), and pack validators (`validate-skill-pack.*`).

- `src.codex/skills/lead/scripts/` — Codex pack: same entity-type co-location pattern (minus the prompt-invocation wrappers, which are Claude-side only).

- `scripts/` (repo root) — co-locates installer scripts (`install-{claude,codex,gemini,qwen}.{sh,ps1}`, `install-hypothesis-hook.py`), agents-mode helpers (`normalize-agents-mode.py`, `sync-agents-mode-docs.py`, `validate-agents-mode-{contract,installers}.py`), work-item helpers (`agent-run-ledger.*`, `check-agent-run-ledger-contract.py`, `check-work-items-state.*`, `validate-work-item-state.*`), and the publication gate (`check-publication-gate.{sh,ps1}`).

**Rationale.** These directories ship as flat units to user projects via `scripts/install-{claude,codex}.{sh,ps1}`. Install scripts hardcode the source-tree paths and the destination-tree paths. User documentation, hooks.json command paths, settings.json command paths, and operator memory of "where things live" all point at these paths. Splitting the directories into per-entity-type subdirectories would force:

- Every existing user install to migrate to a new layout (no clean rollover path for already-installed packs).
- Every Codex/Claude hook entry to update its command path (forcing re-trust on Codex side).
- Every documentation reference and example invocation across `INSTALL.md`, `CLAUDE.md`, `AGENTS.codex.md`, `README.md`, and pack-internal docs to update.

The cost-vs-benefit of forcing this refactor on every existing operator install does not justify the gain from cleaner per-entity-type filesystem layout, because the existing naming convention (`check-*` / `invoke-*` / `validate-*` / `install-*` / etc.) already provides per-entity-type discoverability.

**The exception is grandfathered for wrappers, validators, and installers — and AMENDED for hooks** (decision `work-items/decisions/2026-07-11-hook-placement-gate-semantics.md`). Hook placement follows **gate semantics**, not the generic new-entity-type rule:

- A **warn-only audit hook** (contract: reads its own call's `tool_input`, writes a stderr warning, ALWAYS allows, fails open) → the typed `agents/hooks/` / `skills/lead/hooks/` dir, byte-identical to its `scripts/universal-hooks/hooks/` canon source (set-equality-gated by `tests/test_universal_hook_surfaces.py`).
- A **blocking-enforcement hook** (PreToolUse `permissionDecision: deny` / Stop `decision: block` payloads) or a **SessionStart context hook** → the co-located `agents/scripts/` / `skills/lead/hooks/`-sibling `scripts/` dir beside `hook_common.py`. A universal one is byte-identical to its `scripts/universal-hooks/scripts/` canon source; a provider-specialized one (per-provider config paths or directive wording, e.g. `agents-mode-reminder.*`) carries NO canon copy and is instead DECLARED, with a justification, in the gate's per-pack allowlist (`PACK_ONLY_SCRIPTS` in `tests/test_universal_hook_surfaces.py`). An undeclared scripts/-dir hook fails the gate.
- A new wrapper → typed subdirectory under `agents/wrappers/`, NOT alongside the co-located legacy dir.
- A new validator → typed subdirectory under `validators/`, NOT into root `scripts/` if its lifecycle differs from existing co-located items.

Rationale for the hook amendment: proximity to `hook_common.py` is a placement convention, not an import necessity — the audit hooks in `agents/hooks/` import `hook_common` across directories via an explicit `sys.path` shim. The axis that actually held in practice is gate semantics: `agents/hooks/` is the coherent warn-only-audit family (one identical I/O contract), while blocking and session-context hooks share the envelope-consuming runtime family in `agents/scripts/`. When in doubt, evaluate per the Rule 1 classification test (owner/lifecycle + I/O contract). The presence of these co-located directories is NOT permission to add a fourth co-located dir, nor to grow them with entity types other than the hook classes named above.

## Per-rule worked examples

### Rule 1 — Directory-level entity separation

**Example: adding a new structural-enforcement hook.**

A future maintainer wants to add `check-active-probe-discipline.{py,sh,ps1}` (catches "agent claimed X is unavailable without probe"). The classification:

- Actor/lifecycle: Stop event runtime hook, fired by Claude/Codex CLI's PreToolUse/Stop hook surface.
- I/O contract: reads PreToolUse Stop envelope from stdin; writes `{"decision":"block","reason":"..."}` to stdout or exits 0.

This matches the existing hook entity family (same owner: runtime hook system; same contract: stdin JSON envelope → stdout block payload). **Per the amended placement law**, gate semantics decide the dir: this hook BLOCKS (emits `{"decision":"block"}`), so it belongs in the co-located `agents/scripts/` / `skills/lead/scripts/` dir beside `hook_common.py`, with a byte-identical canon copy added to `scripts/universal-hooks/scripts/` (the parity test picks it up automatically — the name lists are glob-derived from the canon dir).

Had the same hook been a warn-only audit instead (stderr warning, always allow), it would belong in the typed `agents/hooks/` / `skills/lead/hooks/` dir with its canon copy in `scripts/universal-hooks/hooks/`. And had it been provider-specialized (different config paths or directive text per provider, like `agents-mode-reminder.*`), it would ship per-pack in `scripts/` with NO canon copy and a justified entry in the gate's `PACK_ONLY_SCRIPTS` allowlist.

### Rule 2 — Trash hygiene and archival

**Example: replacing a script.**

A maintainer rewrites `scripts/validate-agents-mode-contract.py` into `scripts/validate-agents-mode-contract-v2.py` because the v2 changes the public CLI surface and adopters need migration time.

- If the v1 file is preserved in `git log` and migration docs reference both versions for ~1 release → keep v1 in place temporarily with a `# DEPRECATED: replaced by validate-agents-mode-contract-v2.py — remove after 2026-Q3` header comment.
- If v1 has no callers and serves only history → delete it; git history preserves the file.
- If v1 captures a hard-won bug fix logic that v2 might lose → move to `scripts/archive/validate-agents-mode-contract-v1.py` with a one-line breadcrumb in `scripts/README.md` explaining why archived.

Subject to `Worktree safety`: do not delete or move v1 files that aren't part of the v2-replacement task. Restrict archival to files inside the admitted change surface.

## Cross-references

- Shared rules: `shared/AGENTS.shared.md` `### Scope and ownership discipline`.
- Per-pack maintenance overlays: `AGENTS.md` (Codex maintainer overlay), `CLAUDE.md` (Claude maintainer overlay) — both point at this reference.
- Related rules: `Worktree safety` (`shared/AGENTS.shared.md` `### Operational and environment safety`), `Change-surface minimization`, `Ownership / extension-seam hygiene`, `Interface and encapsulation hygiene`.

## Terms and Abbreviations

- **Entity type**: the kind of work a source file does, classified by actor/lifecycle plus input/output contract.
- **Grandfathered exception**: a documented co-located directory that exists for a deliberate design constraint, exempt from the per-entity-type split; for hooks the placement register is the gate-semantics law above, for other entity types the exception is closed to new contents.
- **Worktree safety**: the existing rule against modifying files outside the admitted change surface (`shared/AGENTS.shared.md` `### Operational and environment safety`).
- **Classification test**: the two-signal placement check (actor/lifecycle + I/O contract) applied before adding or moving any source file.
- **Repo-local concretization**: per-repo extension of a shared rule, declared in `AGENTS.md` / `CLAUDE.md` or in a repo-specific shared reference like this document.
