# Scoring Anchors

Primary scoring weight belongs to semantic correctness, staged re-entry, review handling, and patch
budget discipline. Output size is capped so the scorer does not become a verbosity leaderboard.

Runtime, quota, no-summary, provider tool-loop, and wrapper timeout failures remain runtime caveats
unless the worker produced a completed summary and failed the verifier.
