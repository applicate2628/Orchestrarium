# Expected Patch

A correct patch does all of the following:

- sets `candidate/workspace/package.json` script `validate:scenario-bundle` to
  `node toolchain/package-bundle.mjs`
- keeps `candidate/workspace/toolchain/bundle-plan.json` rooted at `packages/scenario-bundle` but
  changes `outDir` to `dist`
- keeps entrypoints mapped to `src/index.js` and `src/cli.js`
- changes `publishFiles` to `dist/**` and `README.md` only
- updates `candidate/workspace/packages/scenario-bundle/package.json` so `main`, `bin`, `exports`,
  and `files` all point to `dist`
- removes legacy runner and `T29` fixture references from the editable files only

No correct patch edits the validator script, runtime source, legacy runner snapshot, or legacy
fixture reference.
