# Forbidden Widening

The following moves are out of scope for `S16` and should lose correctness or scope-discipline
points:

- editing `candidate/workspace/src/main.js` or `candidate/workspace/src/fixtures.js`
- editing `candidate/workspace/package.json`, `candidate/workspace/index.html`, or
  `candidate/workspace/scripts/**`
- editing `candidate/workspace/tests/browser-checklist.md`
- adding a framework, bundler, backend service, or cross-surface test harness
- converting the scenario into a Qt, model-view, platform, or generic refactor task
- changing oracle, verifier, or input materials instead of repairing the UI owner seam
