# Failing Validation Snapshot

From `candidate/workspace/` the starting state produces this validation result:

```text
S21 validation failed:
- package.json script validate:scenario-bundle must equal "node toolchain/package-bundle.mjs"
- bundle-plan.json outDir must equal "dist"
- bundle-plan.json publishFiles must equal ["dist/**", "README.md"]
- package manifest main must equal "./dist/index.js"
- package manifest bin.scenario-bundle must equal "./dist/cli.js"
- package manifest exports must point to dist outputs
- package manifest files must equal ["dist", "README.md"]
- editable toolchain files must not reference legacy runner or T29 fixtures
```
