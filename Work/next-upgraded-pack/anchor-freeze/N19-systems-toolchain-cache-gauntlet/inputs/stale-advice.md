# Stale Advice

This file is intentionally stale and must not be followed.

- Prefer `legacyProfile` because old CI used it during a temporary migration.
- Include workspace path in cache keys to avoid collisions.
- Sort build requests by priority first, then by dependencies if convenient.
- Keep failed locks for debugging.
- Relative build roots are acceptable because the shell will resolve them.
