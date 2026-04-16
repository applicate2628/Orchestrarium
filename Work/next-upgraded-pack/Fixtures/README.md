Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This directory is reserved for the next upgraded pack fixtures.

Store here:

- new or upgraded test fixtures
- fixture-local notes needed for execution
- verifier surfaces for the mutable next pack

Current active scaffolds:

- `retrofit-batch-1/`
- `T29-toolchain-false-root-ambiguity/`
- `T30-static-ui-wrong-file-attraction/`

Current concrete fixtures:

- `T29-toolchain-false-root-ambiguity/` now has `broken/` and `control-pass/` runnable copies
- `T30-static-ui-wrong-file-attraction/` now has `broken/` and `control-pass/` runnable copies
- `retrofit-batch-1/T08-provider-local-note-fix/` now has `broken/` and `control-pass/` runnable copies
- `retrofit-batch-1/T09-root-cause-owner-debug/` now has `broken/` and `control-pass/` runnable copies
- `retrofit-batch-1/T10-resume-stale-context-rejection/` now has `broken/` and `control-pass/` runnable copies
- `retrofit-batch-1/T22-build-owner-continuity/` now has `broken/` and `control-pass/` runnable copies
- `retrofit-batch-1/T23-path-recall-continuity/` now has `broken/` and `control-pass/` runnable copies
- `retrofit-batch-1/T24-multi-step-worker-persistence/` now has `broken/` and `control-pass/` runnable copies
- `retrofit-batch-1/T25-messy-worker-ownership/` now has `broken/` and `control-pass/` runnable copies
- `retrofit-batch-1/` remains the mutable implementation zone for the rest of the retrofit slice
