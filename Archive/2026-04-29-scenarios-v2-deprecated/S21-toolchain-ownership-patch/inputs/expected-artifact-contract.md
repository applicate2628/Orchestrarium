# Expected Artifact Contract

The repaired package must satisfy all of the following:

- validation command: `node toolchain/package-bundle.mjs`
- package root: `packages/scenario-bundle`
- output directory: `dist`
- entrypoints: `src/index.js` for `.` and `src/cli.js` for `./cli`
- published files: `dist/**` and `README.md` only
- manifest targets: `main`, `exports`, and `bin` point to `./dist/...`
- legacy references to `T29` fixtures or `run-active-cohort-batch.ps1` are removed from editable
  files
- runtime source remains unchanged
