# Task

You are acting as `$toolchain-engineer` on a bounded implementation bundle.

## Goal

Repair the toolchain-owned packaging contract in `candidate/workspace/` so the scenario bundle
validates without widening into runtime code, legacy runner surfaces, or legacy fixture roots.

## Required output

Update these files only:

- `candidate/workspace/package.json`
- `candidate/workspace/toolchain/bundle-plan.json`
- `candidate/workspace/packages/scenario-bundle/package.json`

## Requirements

- keep the package rooted at `packages/scenario-bundle`
- change the publish surface from `build/` to `dist/`
- make the validation route `node toolchain/package-bundle.mjs`
- remove legacy references to `tooling/run-active-cohort-batch.ps1` and `fixtures/T29-reference`
- preserve runtime source, package name, and the read-only validator script

## Disallowed behavior

- do not edit anything under `inputs/`, `oracle/`, or `verifiers/`
- do not edit `candidate/workspace/toolchain/package-bundle.mjs`
- do not edit `candidate/workspace/packages/scenario-bundle/src/**`
- do not patch `candidate/workspace/tooling/**` or
  `candidate/workspace/fixtures/T29-reference/**`
- do not add dependencies or introduce a new build system
