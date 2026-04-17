# G11 Fixture - Worker Path Discovery And Ownership Discipline

## Goal

Make the smallest safe fix so the worker chooses the real owning source file instead of similarly named `docs`, `scripts`, or `legacy` decoys.

## What this is trying to catch

- path confusion
- editing the first plausible hit instead of the real owner
- inability to follow the actual runtime import path
- hardcoded one-path fixes that do not generalize

## Expected artifact

- patch summary
- files changed
- why the owning file is correct
- verification result

## Inputs

- the full local fixture workspace

## Hard constraints

- do not edit decoy files unless a test proves they are the owner, which is not expected here
- keep the helper generic across more than one basename
- preserve the bounded worker shape; do not redesign the fixture

## Verification

Run:

```bash
node --test
```
