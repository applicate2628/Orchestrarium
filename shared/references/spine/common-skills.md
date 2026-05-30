# Common skills — full reference

Common skills are workflow-focused capabilities that any role or the main conversation can invoke when the skill's description matches the current task. They are not roles and do not own delivery; they package reusable methodology, gates, and evidence requirements for a specific kind of work. The always-loaded spine keeps the skill names; this reference holds the archetypes, installed layout, and per-skill descriptions.

Two archetypes:
- **Knowledge-style**: loaded into the caller's current context to inform how the caller performs work; no separate execution lane. Example: `$mathtype-book-page`.
- **Delegate-style**: spawnable as a fresh-context subagent that executes the workflow and returns one self-contained artifact; also invocable inline via the skill loader when fresh context is not needed. Example: `$windows-gui-manual-testing`.

Discovery, invocation, and installed layout:
- Codex installs them under `skills/<name>/` next to role skills. Every skill in this tree carries `agents/openai.yaml` so Codex can uniformly register `$<name>` as a spawnable subagent; the archetype distinction is informational on this side. Knowledge-style skills typically use the subagent prompt to load the workflow body, while delegate-style skills also produce a self-contained findings artifact.
- Claude installs them under `.claude/skills/<name>/` so the `Skill` tool can invoke them. Delegate-style additionally installs a thin wrapper at `.claude/agents/<name>.md` so the main conversation can spawn a fresh-context subagent via the Agent tool; knowledge-style ships only the `Skill`-tool form. Both archetypes remain reachable by every role with `Skill` tool access.
- Gemini and Qwen install them under their installed extension root's `skills/<name>/` directory (for example `.gemini/extensions/orchestrarium-gemini/skills/<name>/`, not the source-tree `src.gemini/skills/`) and rely on each runtime's native skill resolver; subagent-style fresh-context delegation is not modeled there.

Common-skill index (installed names):
- `$windows-gui-manual-testing` — delegate-style. Windows desktop GUI manual visual verification with screenshots, video frames, or live inspection across toolkit/runtime variants; owns screen capture when no recording exists, hard crop validation, and structural-vs-cosmetic classification of UI issues. Returns an evidence-backed findings package.
- `$analyzing-video-bugs` — knowledge-style. Extract frames from any UI/animation/layout bug video (user-provided or agent-captured), locate scene transitions, dense-sample around transitions, read the smallest distinguishing frame set.
- `$bug-hunting` — knowledge-style. Systematic runtime bug investigation via diagnostic logging: log first, never patch on unverified theory, never re-roll on guesses, remove diagnostics in the same commit cycle as the fix.
- `$mathtype-book-page` — knowledge-style. Bring translated technical-book DOCX pages to accepted MathType format with source-PDF authority, gate discipline, and defective-chunk repair workflow.

## Terms and Abbreviations

Domain terms, role names, status labels, and abbreviations used above are defined in the shared governance glossary: `shared/references/spine/governance-glossary.md`.
