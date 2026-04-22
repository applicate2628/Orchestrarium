# Current Failure Evidence

- `child-linux` can be planned before `base-linux` because priority currently overrides dependency order.
- cache keys include request workspace paths, so the same build misses cache on different machines.
- `BUILDGATE_BUILD_ROOT=relative/cache` is accepted and later leaks into artifact paths.
- lock state can remain active after a failed target.
- stale legacy profile settings can override the active profile.
