# Orchestrarium V1 parity baseline

This directory anchors Stage 0 of the Orche 2.0 migration.

## Immutable source

- Repository: `applicate2628/Orchestrarium`
- Source branch at capture time: `main`
- Accepted commit: `ce2052fb773576fd6e3206c2a7e21e01852d556b`
- Git tree: `04dccf4575f17c9c5533474d2e0fd1503bfeceb7`
- Intended signed tag: `orchestrarium-v1-parity-baseline`

The baseline is pinned directly to the immutable `main` commit above. It does not depend on,
inherit from, or modify any other pull-request branch. The generator reads the Git object
rather than the working tree, so later branch changes cannot alter this snapshot.

## Local-only verification

Stage 0 intentionally does **not** use GitHub Actions. Verification runs in a local clone and
writes generated evidence under `.scratch/`, which is not a second source of truth.

Run the focused Stage 0 tests:

```bash
python tests/test_orche_baseline_pin.py
python tests/test_orche_pytest_baseline.py
python tests/test_orche_baseline_inventory.py
python tests/test_orche_target_effect_baseline.py
python tests/test_orche_command_baseline.py
```

Generate the immutable inventories and target-effect snapshot locally:

```bash
rm -rf .scratch/orche-stage0
python scripts/baseline/build_inventory.py \
  --repo-root . \
  --repository applicate2628/Orchestrarium \
  --ref ce2052fb773576fd6e3206c2a7e21e01852d556b \
  --output-dir .scratch/orche-stage0/orchestrarium-v1

python scripts/baseline/build_target_effect_baseline.py \
  --inventory .scratch/orche-stage0/orchestrarium-v1/capability-inventory.json \
  --output .scratch/orche-stage0/orchestrarium-v1/target-effect-baseline.json
```

Run the candidate-side validators after the full baseline/candidate differential suite:

```bash
python scripts/validate-agents-spine.py --spine shared/AGENTS.shared.md
python scripts/sync-universal-hooks.py --check
python scripts/validate-agents-mode-installers.py --root .
```

The differential comparator remains available at
`scripts/baseline/compare_pytest_baseline.py`. Run the full baseline and candidate pytest
suites in separate temporary worktrees and isolated home directories, emit JUnit XML for
both, then pass those two files to the comparator. Existing baseline failures may resolve;
new failures, disappeared tests, or failures hidden by skip remain blocking.

## Committed files

- `baseline-pin.json` — immutable commit/tree identity and the local-evidence contract.
- `README.md` — reproduction and acceptance instructions.

The large capability, test, summary, generated `baseline-manifest.json`, and target-effect
outputs are written only to the selected local output directory. They are not committed.
This keeps review noise and merge conflicts low while preserving an exact, reproducible source
through the pinned commit and tree.

## Signed tag gate

The pin does not impersonate a cryptographic signature. After this Stage 0 change is accepted,
a repository owner must create and push the signed tag using an approved GPG or SSH signing key:

```bash
git tag -s orchestrarium-v1-parity-baseline \
  ce2052fb773576fd6e3206c2a7e21e01852d556b \
  -m "Immutable Orchestrarium V1 parity baseline for Orche 2.0"
git push origin orchestrarium-v1-parity-baseline
```

Until the tag exists and verifies, the cryptographic Stage 0 gate remains `BLOCKED` even when
all local differential and validator checks pass.
