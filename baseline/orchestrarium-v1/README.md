# Orchestrarium Version 1 (V1) parity baseline

This directory anchors Stage 0 of the Orche 2.0 migration. It freezes the accepted Version 1 behavior before package migration or semantic refactoring and provides a local, reproducible parity gate.

## Table of contents

- [Immutable source](#immutable-source)
- [Verification model](#verification-model)
- [Canonical invocation](#canonical-invocation)
- [Evidence lifecycle and acceptance](#evidence-lifecycle-and-acceptance)
- [Recovery mode](#recovery-mode)
- [Publication gate](#publication-gate)
- [Terms and Abbreviations](#terms-and-abbreviations)

## Immutable source

- Repository: `applicate2628/Orchestrarium`
- Accepted commit: `ce2052fb773576fd6e3206c2a7e21e01852d556b`
- Git tree: `04dccf4575f17c9c5533474d2e0fd1503bfeceb7`
- Intended signed tag: `orchestrarium-v1-parity-baseline`

The baseline points directly to immutable `main`. It does not inherit another pull-request branch.

## Verification model

The reviewed `baseline-pin.json` identifies nine frozen tools and verifier modules by stable path and Git blob Secure Hash Algorithm identity:

1. inventory generator;
2. target-effect generator;
3. complete capability comparator;
4. Pytest differential comparator;
5. validator-command differential comparator;
6. verifier runtime and worktree-integrity module;
7. trusted-evidence and process-isolation module;
8. verification orchestrator;
9. isolated verifier loader.

The verifier performs the operational work rather than duplicating security-sensitive logic in shell documentation. It:

- resolves exact external Python, Git, and Bash executables outside both tested worktrees;
- records each selected executable's canonical path, device, inode, ownership, mode, timestamps, size, and Secure Hash Algorithm 256-bit digest, then revalidates that identity immediately before every launch and again after every untrusted repository lane;
- removes ambient Python, Git, virtual-environment, and provider-home state;
- disables Git replacement objects through both `GIT_NO_REPLACE_OBJECTS=1` and `git --no-replace-objects` before resolving any reviewed identity or object bytes;
- binds every trusted Git operation to the physically resolved `.git` directory and exact worktree using explicit `--git-dir` and `--work-tree` arguments;
- rejects repository-local Git configuration capable of redirecting the worktree, hiding changes, executing external filters or drivers, altering sparse-checkout behavior, or including additional configuration;
- rejects staged, unstaged, untracked, ignored executable/test/configuration inputs, importable bytecode, hidden Git index flags, and submodule dirtiness;
- keeps frozen tools, lane state, and baseline evidence in separate unique private directories outside both tested worktrees;
- rematerializes and verifies a frozen tool immediately before every execution;
- requires Linux, enables a child subreaper, and sweeps all adopted descendants from `/proc`, so a child cannot escape cleanup by calling `setsid()` or double-forking;
- preserves `PYTHONSAFEPATH=1` while explicitly exposing only the already verified lane worktree as `PYTHONPATH` to repository tests and validators;
- inventories both the pinned baseline and exact reviewed candidate commit;
- treats path, content digest, Git mode, and Git object type as capability identity, so executable-bit and symbolic-link changes cannot disappear behind unchanged file bytes;
- requires an exact reviewed disposition for every added, modified, or removed tracked path;
- compares Pytest exits, JUnit Extensible Markup Language diagnostics, retained skip reasons, and baseline test/support source digests;
- runs all repository-standard validators in both worktrees and requires validator-specific terminal success or failure markers even when both commands exit zero;
- rechecks both baseline and candidate worktrees after every untrusted repository-code stage, including each candidate-focused test suite;
- snapshots the complete trusted-tree membership and identity before each untrusted lane, forbids new entries, removals, replacements, symbolic links, hard links, or special files, and verifies the exact tree afterward;
- creates fresh report names on every run and never recursively deletes candidate `.scratch` content;
- copies completed reports to a unique output directory only after the trusted evidence has been accepted.

## Canonical invocation

Run on Linux with Bash. Supply two clean worktrees, the exact full candidate commit, and canonical non-symlink executable paths. The bootstrap sanitizes the environment before reading the pin or resolving Git objects, disables Git replacement objects, verifies the frozen verifier blobs in the reviewed tree, and invokes the wrapper with Python isolated mode.

```bash
set -euo pipefail

BASELINE_ROOT=/absolute/path/to/baseline-worktree
CANDIDATE_ROOT=/absolute/path/to/candidate-worktree
REVIEWED_REF='<exact-40-character-candidate-commit-sha>'
VERIFIER_PYTHON=/absolute/canonical/path/to/python3
VERIFIER_GIT=/absolute/canonical/path/to/git
VERIFIER_BASH=/absolute/canonical/path/to/bash

BASELINE_ROOT="$(cd -P -- "$BASELINE_ROOT" && printf '%s\n' "$PWD")"
CANDIDATE_ROOT="$(cd -P -- "$CANDIDATE_ROOT" && printf '%s\n' "$PWD")"

assert_canonical_external() {
  tool="$1"
  test "${tool#/}" != "$tool" && test -x "$tool" && test ! -L "$tool" || {
    echo "BLOCKED: verifier path must be an absolute executable non-symlink: $tool" >&2
    return 1
  }
  tool_dir="${tool%/*}"
  tool_base="${tool##*/}"
  canonical="$(cd -P -- "$tool_dir" && printf '%s/%s\n' "$PWD" "$tool_base")"
  test "$tool" = "$canonical" || {
    echo "BLOCKED: verifier path is not canonical: $tool -> $canonical" >&2
    return 1
  }
  case "$canonical" in
    "$BASELINE_ROOT"/*|"$CANDIDATE_ROOT"/*)
      echo "BLOCKED: verifier executable is inside a tested worktree: $canonical" >&2
      return 1
      ;;
  esac
}

assert_canonical_external "$VERIFIER_PYTHON"
assert_canonical_external "$VERIFIER_GIT"
assert_canonical_external "$VERIFIER_BASH"

case "$REVIEWED_REF" in
  ''|*[!0-9a-f]*)
    echo "BLOCKED: REVIEWED_REF must be an exact lowercase hexadecimal commit identifier" >&2
    exit 1
    ;;
esac
case "${#REVIEWED_REF}" in
  40|64) ;;
  *)
    echo "BLOCKED: REVIEWED_REF must contain exactly 40 or 64 hexadecimal characters" >&2
    exit 1
    ;;
esac

VERIFIER_PATH="${VERIFIER_PYTHON%/*}:${VERIFIER_GIT%/*}:${VERIFIER_BASH%/*}:/usr/local/bin:/usr/bin:/bin"
BOOTSTRAP_ROOT="$(
  env -i PATH="$VERIFIER_PATH" HOME=/ TMPDIR=/tmp PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
    "$VERIFIER_PYTHON" -I -c 'import tempfile; print(tempfile.mkdtemp(prefix="orche-stage0-bootstrap-"))'
)"
: > "$BOOTSTRAP_ROOT/gitconfig"

trusted_git() {
  env -i PATH="$VERIFIER_PATH" HOME="$BOOTSTRAP_ROOT" TMPDIR="$BOOTSTRAP_ROOT" \
    GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL="$BOOTSTRAP_ROOT/gitconfig" \
    GIT_NO_REPLACE_OBJECTS=1 \
    "$VERIFIER_GIT" --no-replace-objects "$@"
}
trusted_python() {
  env -i PATH="$VERIFIER_PATH" HOME="$BOOTSTRAP_ROOT" TMPDIR="$BOOTSTRAP_ROOT" \
    PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1 \
    "$VERIFIER_PYTHON" -I "$@"
}
cleanup_bootstrap() {
  env -i PATH="$VERIFIER_PATH" HOME=/ TMPDIR=/tmp PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
    "$VERIFIER_PYTHON" -I -c \
      'import shutil,sys; shutil.rmtree(sys.argv[1], ignore_errors=True)' "$BOOTSTRAP_ROOT"
}
trap cleanup_bootstrap EXIT

PIN_PATH=baseline/orchestrarium-v1/baseline-pin.json
RESOLVED_REVIEWED_REF="$(trusted_git -C "$CANDIDATE_ROOT" rev-parse --verify "$REVIEWED_REF^{commit}")"
test "$REVIEWED_REF" = "$RESOLVED_REVIEWED_REF" || {
  echo "BLOCKED: REVIEWED_REF must name the exact reviewed commit" >&2
  exit 1
}
PIN_JSON="$(trusted_git -C "$CANDIDATE_ROOT" show "$REVIEWED_REF:$PIN_PATH")"
materialize_bootstrap_tool() {
  key="$1"
  destination="$2"
  tool_path="$(
    printf '%s' "$PIN_JSON" | trusted_python -c \
      'import json,sys; print(json.load(sys.stdin)["tooling"][sys.argv[1]]["path"])' "$key"
  )"
  tool_blob="$(
    printf '%s' "$PIN_JSON" | trusted_python -c \
      'import json,sys; print(json.load(sys.stdin)["tooling"][sys.argv[1]]["gitBlobSha"])' "$key"
  )"
  tree_entry="$(trusted_git -C "$CANDIDATE_ROOT" ls-tree "$REVIEWED_REF" -- "$tool_path")"
  test "$(printf '%s\n' "$tree_entry" | trusted_python -c 'import sys; print(sys.stdin.read().split(None, 3)[2])')" = "$tool_blob" || {
    echo "BLOCKED: reviewed bootstrap tool blob mismatch: $key" >&2
    exit 1
  }
  trusted_git -C "$CANDIDATE_ROOT" cat-file blob "$tool_blob" > "$BOOTSTRAP_ROOT/$destination"
  test "$(trusted_git -C "$CANDIDATE_ROOT" hash-object "$BOOTSTRAP_ROOT/$destination")" = "$tool_blob" || {
    echo "BLOCKED: materialized bootstrap tool hash mismatch: $key" >&2
    exit 1
  }
}
materialize_bootstrap_tool stage0Runtime stage0_runtime.py
materialize_bootstrap_tool stage0Evidence stage0_evidence.py
materialize_bootstrap_tool stage0Orchestrator stage0_orchestrator.py
materialize_bootstrap_tool stage0Verifier verify_stage0.py

trusted_python "$BOOTSTRAP_ROOT/verify_stage0.py" \
  --baseline-root "$BASELINE_ROOT" \
  --candidate-root "$CANDIDATE_ROOT" \
  --reviewed-ref "$REVIEWED_REF" \
  --verifier-python "$VERIFIER_PYTHON" \
  --verifier-git "$VERIFIER_GIT" \
  --verifier-bash "$VERIFIER_BASH"
```

The bootstrap uses `git cat-file blob` to materialize the reviewed verifier wrapper and its three reviewed modules, verifies every blob, and executes the wrapper with `python -I`. An `EXIT` trap removes the bootstrap directory on every shell completion path. The verifier creates its trusted and lane roots as separate mode-`0700` directories under the real Linux `/tmp`, not beneath the bootstrap directory, so explicit recovery preservation is not erased by the shell trap. The bootstrap directory contains no repository code except those verified frozen verifier blobs. Repository tests and validators receive only their verified worktree through an explicit per-lane `PYTHONPATH`; frozen verifier tools never inherit it.

## Evidence lifecycle and acceptance

Stage 0 is intentionally local-only and does not add a GitHub Actions workflow. A successful run produces:

- immutable baseline and reviewed-candidate capability/test inventories;
- target-effect measurements based on normalized Skill bodies;
- complete tracked-path disposition comparison;
- baseline/candidate Pytest reports and a differential verdict;
- baseline/candidate logs and comparison reports for every repository-standard validator;
- a machine-readable summary bound to both exact commit identifiers.

The external trusted and lane directories are removed after a successful run and, by default, after a failed run. Only the accepted copied report set remains under the candidate's unique `.scratch/orche-stage0/reviewed-runs/<commit>-<random>/` directory. The copied directory is never reused as input evidence.

Exit `0` is accepted evidence. Exit `1` means verified semantic parity is `BLOCKED`. Exit `2` means the evidence is operationally invalid and must not be interpreted as parity drift. Operational Pytest exits, operational validator exits, marker-free successes, and marker-free semantic failures therefore produce exit `2`.

## Recovery mode

For explicit failure investigation only, append `--preserve-failed-evidence` to the verifier command. On failure the verifier prints the external trusted and lane directory paths. This option is not part of the normal acceptance run and preserved state must not be treated as accepted evidence. Delete those directories manually after diagnosis.

## Publication gate

The pin is not a cryptographic signature. Before creating or pushing the signed tag:

1. stage the exact accepted tracked change in a clean publication-review checkout;
2. run `python scripts/check-publication-gate.py` and `git diff --cached --check`;
3. perform a human leak review of the staged diff;
4. obtain approval from a distinct human `$knowledge-archivist`; an exception requires `$security-reviewer`;
5. confirm no tracked bytes changed after approval and the destination is exactly `refs/tags/orchestrarium-v1-parity-baseline`.

Only the repository owner may then create, verify, and push the signed tag. Until those human gates pass, tag publication remains `BLOCKED`.

## Terms and Abbreviations

- **Bash:** Bourne Again Shell, the command interpreter used by the bootstrap.
- **CLI:** Command-Line Interface, a program operated through terminal commands.
- **Git blob:** an immutable Git object containing one file's bytes.
- **Git mode:** the tracked Git file mode, such as regular file, executable file, symbolic link, or submodule entry.
- **JUnit XML:** JUnit Extensible Markup Language, the machine-readable Pytest result format.
- **Linux child subreaper:** a Linux process that adopts orphaned descendants so they remain controllable even after `setsid()` or a double fork.
- **PATH:** the operating-system executable search path.
- **POSIX:** Portable Operating System Interface, the process/session model on which the Linux verifier builds.
- **PR:** Pull Request, a proposed repository change submitted for review.
- **`/proc`:** the Linux process-information filesystem used to identify and reap every lane descendant.
- **Pytest:** the Python test runner used by the repository suite.
- **SHA-256:** Secure Hash Algorithm 256-bit, used for evidence and executable byte digests.
- **Skill:** a repository instruction package whose methodology body is compared independently of provider frontmatter.
- **V1:** Version 1, the accepted legacy behavior frozen before Orche 2.0 migration.
