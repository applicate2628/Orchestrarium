# Spine elaboration extracts

Elaboration files for the always-loaded governance spine
(`shared/AGENTS.shared.md` -> installed `AGENTS.md`). Most began as verbatim
prose extracted during the Task-6 size reduction; newer files may be authored
alongside new compact spine rules. Each file expands a rule whose operational
form remains binding in the spine; roles read these on demand for depth. These
are NOT separate methodology owners (those live at the top level of
`shared/references/` with `ru/` mirrors) - they are English-only depth slices of
the spine. The spine's compact form is self-sufficient for compliance; these
files add operational-test detail, allowed-case elaboration, examples, rationale,
and commit-discipline detail.

**Canon and drift discipline.** The spine (`shared/AGENTS.shared.md`) is the
canonical, binding source. These extracts are depth snapshots: if an extract
ever disagrees with the spine, the spine wins. When you edit a spine rule, update
the matching extract in the same change so the snapshot does not rot and
reintroduce superseded guidance to a role that reads it for depth.
`scripts/validate-agents-spine.py` enforces the spine size cap and the
lose-nothing protection-token manifest, and runs on every `pytest tests/` (via
`tests/test_agents_spine_validator.py`) so a dropped protection token or an
over-cap spine fails the suite. It does not yet diff extract prose against the
spine, so keeping the extracts in sync with the spine is a maintainer
responsibility; the manifest is a token-presence and size check, not a
semantic-binding check (it would not catch a rule reworded from MUST to optional
while its pinned token stays present).

## Terms and Abbreviations

Domain terms (spine, manifest, protection token, extract) are defined inline
above; governance role names, status labels, and provider terms used by the
extracts are defined in `shared/references/spine/governance-glossary.md`.
