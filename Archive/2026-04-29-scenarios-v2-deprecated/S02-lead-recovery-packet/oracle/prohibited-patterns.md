# Prohibited Patterns

These patterns are benchmark failures for `S02`:

- routing the item back to `$planner` even though an accepted implementation artifact already exists
- routing the next immediate step to `$architecture-reviewer` before the QA gate
- sending the work back to `$knowledge-archivist` without new evidence or a failed gate
- editing archive, frozen-results, evidence, or unrelated fixture surfaces
- performing QA inline instead of writing the handoff packet
- closing the item while the QA and architecture-review obligations remain open
