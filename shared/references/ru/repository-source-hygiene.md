# Repository Source Hygiene — Reference

Этот reference document для правил организации source-tree `Directory-level entity separation` и `Trash hygiene and archival`, определённых в `shared/AGENTS.shared.md` `### Scope and ownership discipline`. **НЕ** устанавливается в target projects — это methodology reference + repo-local concretization для этого monorepo.

## Краткое описание правил

Два правила управляют source-tree hygiene:

1. **Directory-level entity separation** — каждая source directory имеет один primary entity type и ownership/lifecycle contract; назначение directory выражается одним предложением; новые файлы размещаются после классификации по owner/lifecycle + I/O contract.
2. **Trash hygiene and archival** — удалять или архивировать obsolete files внутри admitted change surface, subject to `Worktree safety`; archival path с breadcrumb если deletion потеряет recoverable history.

## Что считается "entity type"

Entity type — это **вид работы, который делает файл**, классифицируется по:

- **Актор / lifecycle, который владеет или вызывает файл.** Runtime hook (PreToolUse/Stop, вызывается Claude/Codex CLI); agent-side wrapper (вызывается агентом во время сессии через tool); installer (вызывается maintainer'ом во время `--global` install); validator (вызывается CI или maintainer'ом); gate (deny-on-fail check перед publication action); skill/command (вызывается агентом через Skill или slash-command); runtime helper (вызывается user'ом или scripts в target projects после install).

- **Input/output contract или side effects.** Что файл потребляет (stdin envelope / argv / config file / file-system state) и что производит (structured-deny JSON / exit code / written file / git ref / log entry). Два файла с одинаковым contract — один entity type; с разным contract — разные entity types.

Platform variants (`.sh`/`.ps1`/`.py`) той же команды с тем же contract считаются **одним entity**, не несколькими.

## Grandfathered exceptions этого репо

`shared/AGENTS.shared.md` `Directory-level entity separation` требует чтобы directories организовывались вокруг одного primary entity type. Orchestrarium monorepo имеет **три намеренно co-located директории**, которые служат documented design constraint и exempt от per-entity-type split:

- `src.claude/agents/scripts/` — Claude pack: co-locates runtime hooks (`check-bugfix-discipline.*`, `check-passive-polling-stop.*`, `hook_common.py`), provider invocation wrappers (`invoke-claude-api.*`, `invoke-claude-prompt.*`, `invoke-codex-prompt.*`), publication gates (`check-publication-safety.*`), и pack validators (`validate-skill-pack.*`).

- `src.codex/skills/lead/scripts/` — Codex pack: тот же entity-type co-location pattern (минус prompt-invocation wrappers, которые Claude-side only).

- `scripts/` (repo root) — co-locates installer scripts (`install-{claude,codex,gemini,qwen}.{sh,ps1}`, `install-hypothesis-hook.py`), agents-mode helpers (`normalize-agents-mode.py`, `sync-agents-mode-docs.py`, `validate-agents-mode-{contract,installers}.py`), work-item helpers (`agent-run-ledger.*`, `check-agent-run-ledger-contract.py`, `check-work-items-state.*`, `validate-work-item-state.*`), и publication gate (`check-publication-gate.{sh,ps1}`).

**Rationale.** Эти directories ship как flat units в user projects через `scripts/install-{claude,codex}.{sh,ps1}`. Install scripts hardcode source-tree paths и destination-tree paths. User documentation, hooks.json command paths, settings.json command paths, и operator memory "где что лежит" — всё указывает на эти paths. Split directories в per-entity-type subdirectories вынудил бы:

- Каждый existing user install мигрировать на new layout (нет clean rollover path для уже-installed packs).
- Каждый Codex/Claude hook entry update'ить command path (forced re-trust на Codex side).
- Каждый documentation reference и example invocation в `INSTALL.md`, `CLAUDE.md`, `AGENTS.codex.md`, `README.md`, и pack-internal docs обновить.

Cost-vs-benefit принудительного refactor'а на каждый existing operator install не оправдывает gain от cleaner per-entity-type filesystem layout, потому что existing naming convention (`check-*` / `invoke-*` / `validate-*` / `install-*` / etc.) уже даёт per-entity-type discoverability.

**Exception grandfathered, не extensible.** Новые entity types добавленные в будущем ДОЛЖНЫ следовать shared rule:

- Новый hook → typed subdirectory под `agents/hooks/` или `skills/lead/hooks/` (создавать subdirectory если её ещё нет), НЕ в co-located legacy dir.
- Новый wrapper → typed subdirectory под `agents/wrappers/`, НЕ рядом с co-located legacy dir.
- Новый validator → typed subdirectory под `validators/`, НЕ в root `scripts/` если его lifecycle отличается от existing co-located items.
- Etc.

В случае сомнения, оценивать по Rule 1 classification test (owner/lifecycle + I/O contract). Наличие трёх legacy co-located директорий не constitutes permission добавить четвёртую или grow existing three.

## Per-rule worked examples

### Rule 1 — Directory-level entity separation

**Пример: добавление нового structural-enforcement hook.**

Будущий maintainer хочет добавить `check-active-probe-discipline.{py,sh,ps1}` (ловит "agent claimed X is unavailable without probe"). Классификация:

- Actor/lifecycle: Stop event runtime hook, fired by Claude/Codex CLI's PreToolUse/Stop hook surface.
- I/O contract: reads PreToolUse Stop envelope from stdin; writes `{"decision":"block","reason":"..."}` to stdout или exits 0.

Это matches existing hook entity type (тот же owner: runtime hook system; тот же contract: stdin JSON envelope → stdout deny payload). **Per the grandfathered exception**, новый hook принадлежит в новой typed subdirectory `agents/hooks/` (создаваемой для этого first new-entity-type hook'а), НЕ в legacy `agents/scripts/` co-located dir.

Если бы grandfathered exception не существовал, новый hook принадлежал бы в том же месте, где он сейчас (typed subdir). Exception merely formalizes что **existing** files остаются где они, **new** files следуют правилу.

### Rule 2 — Trash hygiene and archival

**Пример: замена script'а.**

Maintainer переписывает `scripts/validate-agents-mode-contract.py` в `scripts/validate-agents-mode-contract-v2.py`, потому что v2 меняет public CLI surface и adopters'ам нужно migration time.

- Если v1 file preserved в `git log` и migration docs reference обе версии для ~1 release → keep v1 in place temporarily с `# DEPRECATED: replaced by validate-agents-mode-contract-v2.py — remove after 2026-Q3` header comment.
- Если v1 не имеет callers и serves only history → delete it; git history preserves the file.
- Если v1 captures hard-won bug fix logic, которую v2 might lose → move to `scripts/archive/validate-agents-mode-contract-v1.py` с one-line breadcrumb в `scripts/README.md` объясняющим why archived.

Subject to `Worktree safety`: не удалять или двигать v1 files которые не часть v2-replacement task. Restrict archival к files внутри admitted change surface.

## Cross-references

- Shared rules: `shared/AGENTS.shared.md` `### Scope and ownership discipline`.
- Per-pack maintenance overlays: `AGENTS.md` (Codex maintainer overlay), `CLAUDE.md` (Claude maintainer overlay) — оба указывают на этот reference.
- Related rules: `Worktree safety` (`shared/AGENTS.shared.md` `### Operational and environment safety`), `Change-surface minimization`, `Ownership / extension-seam hygiene`, `Interface and encapsulation hygiene`.

## Термины и сокращения

- **Entity type**: вид работы, который делает source file, classified by actor/lifecycle плюс input/output contract.
- **Grandfathered exception**: documented co-located directory, существующая для deliberate design constraint, exempt от per-entity-type split для existing contents но не extensible к new contents.
- **Worktree safety**: существующее правило против модификации файлов вне admitted change surface (`shared/AGENTS.shared.md` `### Operational and environment safety`).
- **Classification test**: two-signal placement check (actor/lifecycle + I/O contract) применённый перед added or moving any source file.
- **Repo-local concretization**: per-repo extension of shared rule, declared в `AGENTS.md` / `CLAUDE.md` или в repo-specific shared reference как этот документ.
