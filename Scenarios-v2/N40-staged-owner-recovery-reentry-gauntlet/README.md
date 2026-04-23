# N40 Staged Owner Recovery Reentry Gauntlet

This diagnostic surface tests owner/orchestration recovery under staged fresh invocations. The
worker must preserve current source truth, reject stale result tables, keep lane boundaries, apply
runtime/quota classification correctly, and close with a durable resume point.
