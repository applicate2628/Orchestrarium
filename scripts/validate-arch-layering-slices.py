#!/usr/bin/env python3
"""Drift gate for the distributed 'Architecture layering hygiene' role slices.

The architecture-layering best-practices live in `shared/references/architecture-layering-hygiene.md`
(maintainer-only, not installed). A compact slice of that reference is inlined into each relevant role
definition in BOTH production packs so the role knows its best-practices at runtime. That inlining
creates duplicated representations of one owned source across role files and across the claude/codex
packs -- which the reference's own law C1 permits ONLY when the copies are generated-from-one-source OR
drift-gated. This script is that drift gate.

It enforces TWO independent drift axes:

  COPY-TO-COPY (internal parity, always checkable where the role files exist):
    1. Every role expected to carry a slice has exactly one '## Architecture layering hygiene...' block.
    2. Within each group (impl / spec / perf), all member roles' blocks are byte-identical (per pack).
    3. For every role, the claude block == the codex block (cross-pack parity; only when both packs exist).

  SOURCE-TO-RUNTIME (the slices are lossy condensations of the reference; a reference edit can leave
  every inlined slice silently stale while the copy-to-copy checks stay green):
    4. The reference's SHA-256 must match the review stamp in `scripts/arch-layering-slices.stamp`.
       The stamp records "the inlined slices were last reviewed for fidelity against THIS reference
       content". When the reference changes, this gate FAILS until a maintainer re-reviews the slices
       for fidelity and re-stamps with `--update-stamp`. This is the C1 drift gate against the source.

KNOWN RESIDUAL (axis 3, accepted; governed by human review at the publication gate): a COHERENT edit
applied identically to every copy of a group, with the reference + stamp left untouched, drifts the slices
from the reference's MEANING yet passes every gate above -- within-group + cross-pack prove the copies
agree WITH EACH OTHER, the stamp proves the reference FILE is unchanged, but nothing ties slice CONTENT to
reference CONTENT, because a lossy condensation cannot be mechanically re-derived from its source. Future
hardening (additive, not yet implemented): store a per-group reviewed-slice hash beside the reference hash,
so a coherent all-copy slice edit also forces an explicit re-review + re-stamp.

Usage:
    python scripts/validate-arch-layering-slices.py [ROOT]          # validate (exit 0 PASS / 1 FAIL)
    python scripts/validate-arch-layering-slices.py [ROOT] --update-stamp   # re-stamp after a re-review

Standalone single-pack checkout: cross-pack parity is skipped (needs both packs); within-group parity
and the source stamp are still enforced for whatever is present. A missing reference (a published
single-provider branch that does not carry shared/references/) skips only the stamp gate.
"""
import hashlib
import re
import sys
from pathlib import Path

# role -> group. Groups with >=2 members must have byte-identical blocks across members.
GROUPS = {
    "impl": [
        "backend-engineer", "frontend-engineer", "data-engineer",
        "model-view-engineer", "qt-ui-engineer", "geometry-engineer",
        "graphics-engineer", "visualization-engineer",
    ],
    "release": ["platform-engineer", "toolchain-engineer"],
    "spec": ["algorithm-scientist", "computational-scientist"],
    "perf": ["performance-engineer", "performance-reviewer"],
    "stability": ["reliability-engineer"],
    "test": ["qa-engineer"],
    "security": ["security-engineer"],
    "design": ["architect"],
    "review": ["architecture-reviewer"],
}

# `\Z` in the lookahead so a hygiene block that is the LAST section (no following `## `) still matches.
BLOCK_RE = re.compile(
    r"^## Architecture layering hygiene.*?(?=^## |\Z)",
    re.MULTILINE | re.DOTALL,
)

REFERENCE_REL = "shared/references/architecture-layering-hygiene.md"
STAMP_REL = "scripts/arch-layering-slices.stamp"


def claude_path(root: Path, role: str) -> Path:
    return root / "src.claude" / "agents" / f"{role}.md"


def codex_path(root: Path, role: str) -> Path:
    return root / "src.codex" / "skills" / role / "SKILL.md"


def extract_block(path: Path):
    """Return (block, None) for exactly one hygiene block, else (None, reason)."""
    if not path.exists():
        return None, f"file missing: {path}"
    text = path.read_text(encoding="utf-8")
    blocks = BLOCK_RE.findall(text)
    if len(blocks) == 0:
        return None, f"no '## Architecture layering hygiene' block: {path}"
    if len(blocks) > 1:
        return None, f"{len(blocks)} hygiene blocks (expected 1): {path}"
    return blocks[0].rstrip("\n"), None


def reference_sha(root: Path):
    """SHA-256 of the reference, computed on raw bytes (line-ending agnostic via newline-normalize)."""
    ref = root / REFERENCE_REL
    if not ref.exists():
        return None
    # Normalize CRLF -> LF so a checkout's line-ending policy does not churn the stamp.
    data = ref.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def read_stamp(root: Path):
    p = root / STAMP_REL
    if not p.exists():
        return None
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    return None


def write_stamp(root: Path, sha: str) -> None:
    p = root / STAMP_REL
    p.write_text(
        "# Review stamp for the inlined architecture-layering role slices.\n"
        "# SHA-256 of shared/references/architecture-layering-hygiene.md (CRLF-normalized) that the\n"
        "# inlined slices were last reviewed for fidelity against. Regenerate with:\n"
        "#   python scripts/validate-arch-layering-slices.py --update-stamp\n"
        "# ONLY after re-reviewing every role slice against the changed reference.\n"
        f"{sha}\n",
        encoding="utf-8",
    )


def main() -> int:
    argv = sys.argv[1:]
    update = "--update-stamp" in argv
    positional = [a for a in argv if not a.startswith("-")]
    root = Path(positional[0]) if positional else Path.cwd()

    if update:
        sha = reference_sha(root)
        if sha is None:
            print(f"ERROR: reference not found at {root / REFERENCE_REL}; cannot stamp")
            return 2
        write_stamp(root, sha)
        print(f"stamped: {sha}")
        return 0

    claude_present = (root / "src.claude" / "agents").is_dir()
    codex_present = (root / "src.codex" / "skills").is_dir()
    packs = [p for p, ok in (("claude", claude_present), ("codex", codex_present)) if ok]
    if not packs:
        print("SKIP: no role pack present (src.claude / src.codex both absent)")
        return 0

    failures = []
    notes = []

    # Collect blocks per role for each present pack.
    blocks = {}  # role -> {pack: str|None}
    for group, roles in GROUPS.items():
        for role in roles:
            blocks[role] = {}
            for pack in packs:
                path = claude_path(root, role) if pack == "claude" else codex_path(root, role)
                blk, err = extract_block(path)
                if err:
                    failures.append(f"[{group}/{role}/{pack}] {err}")
                blocks[role][pack] = blk

    # 2. Within-group byte-identity, per present pack.
    for group, roles in GROUPS.items():
        if len(roles) < 2:
            continue
        for pack in packs:
            ref_role = roles[0]
            ref = blocks[ref_role].get(pack)
            if ref is None:
                continue
            for role in roles[1:]:
                cur = blocks[role].get(pack)
                if cur is not None and cur != ref:
                    failures.append(
                        f"[{group}/{pack}] slice in '{role}' diverges from group canonical '{ref_role}'"
                    )

    # 3. Cross-pack parity, only when both packs present.
    if claude_present and codex_present:
        for role, per in blocks.items():
            c, x = per.get("claude"), per.get("codex")
            if c is not None and x is not None and c != x:
                failures.append(f"[{role}] claude slice != codex slice (cross-pack drift)")
    else:
        notes.append("cross-pack parity skipped (single-pack checkout)")

    # 4. Source-to-runtime stamp gate (only when the reference travels with the checkout).
    cur_sha = reference_sha(root)
    if cur_sha is None:
        notes.append("source stamp gate skipped (reference not present in this checkout)")
    else:
        stamp = read_stamp(root)
        if stamp is None:
            failures.append(
                "[source] no review stamp at scripts/arch-layering-slices.stamp; review the slices "
                "against the reference then run: python scripts/validate-arch-layering-slices.py --update-stamp"
            )
        elif stamp != cur_sha:
            failures.append(
                "[source] reference changed since the slices were last reviewed "
                f"(stamp {stamp[:12]}... != reference {cur_sha[:12]}...); re-review every role slice for "
                "fidelity, then re-stamp: python scripts/validate-arch-layering-slices.py --update-stamp"
            )

    total = sum(len(r) for r in GROUPS.values())
    for n in notes:
        print(f"NOTE: {n}")
    if failures:
        print(f"FAIL: arch-layering slice drift gate ({len(failures)} issue(s) over {total} roles)")
        for f in failures:
            print(f"  - {f}")
        return 1
    stamp_part = "source stamp matches" if cur_sha is not None else "source stamp skipped (no reference)"
    print(
        f"PASS: arch-layering slices consistent ({total} roles, within-group identical, "
        f"{'claude==codex, ' if claude_present and codex_present else ''}{stamp_part})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
