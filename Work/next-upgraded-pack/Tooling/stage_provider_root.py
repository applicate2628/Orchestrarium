#!/usr/bin/env python3
"""Stage a benchmark bundle into a provider-VISIBLE root that omits the answer key.

Phase-0 harness item H2 (BUILD-PLAN-v2.1). Closes the blind-oracle leak: the legacy runner
copied the WHOLE bundle (incl. oracle/ + verifiers/) into the candidate's working directory, so a
candidate could read the answer key. This tool allowlist-copies only what the candidate legitimately
needs (inputs/, candidate/, README.md, a sanitized scenario.yaml) and hard-fails (structural sentinel,
I3 layer 1) if any oracle/verifier/discrimination path reaches the provider root.

Usage:
  python stage_provider_root.py --bundle <bundlePath> --provider-root <dest> --meta <metaDir>
                                [--sentinel-canary]

Exit 0 on success; non-zero (with a STAGE-FAIL message on stderr) if the sentinel trips or a required
input is missing. Writes <metaDir>/staging-manifest.json (rel path + sha256 of every staged file) and,
in canary mode, <metaDir>/canary.json (the nonce + decoy values the scorer greps for).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import sys
import uuid
from pathlib import Path

_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def _is_reparse_point(path: Path) -> bool:
    """True for a symlink / junction / mount / any reparse point (do not follow)."""
    lst = path.lstat()
    if stat.S_ISLNK(lst.st_mode):
        return True
    return bool(getattr(lst, "st_file_attributes", 0) & _REPARSE)


def _assert_no_reparse(src: Path) -> None:
    """Reject a reparse point anywhere in the source subtree BEFORE copying.

    Without this, shutil.copytree(symlinks=False) would FOLLOW a link such as
    `candidate/alias -> ../oracle`, staging the answer key under an innocent path that the
    path-only sentinel cannot catch (Terra H1 audit, HIGH-3).
    """
    if _is_reparse_point(src):
        raise _StageError(f"reparse point in source (would follow to unknown target): {src}")
    if src.is_dir():
        for child in src.rglob("*"):
            if _is_reparse_point(child):
                raise _StageError(f"reparse point in source subtree: {child}")


class _StageError(Exception):
    pass

# Top-level bundle entries the candidate is allowed to see. scenario.yaml is copied through a
# key-allowlist rewrite (STAGED_YAML_KEYS); everything else here is copied verbatim (recursively for
# directories). Anything NOT in this list — oracle/, verifiers/, discrimination.yaml, stale-*/,
# candidate/stale-advice, etc. — never reaches the provider root.
ALLOWED_TOP_LEVEL = ("inputs", "candidate", "README.md", "scenario.yaml")

# scenario.yaml keys the candidate may see. expected_winner and any future discrimination metadata
# are excluded by DEFAULT (allowlist, not denylist) so a later field addition cannot silently leak.
STAGED_YAML_KEYS = (
    "id",
    "surface_id",
    "pack_id",
    "role_class",
    "artifact_type",
    "modality_family",
    "allowed_change_surface",
    "must_not_touch",
    "score_profile",
    "overlay_flags",
)

# Paths that must NEVER appear under the provider root (checked as `/`-bounded segments).
FORBIDDEN_SEGMENTS = ("oracle", "verifiers")
FORBIDDEN_FILES = ("discrimination.yaml",)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def sanitize_scenario_yaml(src: Path, dest: Path) -> None:
    """Rewrite scenario.yaml keeping only STAGED_YAML_KEYS.

    The bundle scenario.yaml is a flat key/list subset (matching the runner's Read-SimpleScenarioMetadata
    parser): top-level `key:` lines, some followed by indented `  - item` list lines. We keep a key's
    line plus its indented continuation lines iff the key is allowlisted. Dependency-free by design
    (no PyYAML) so the security-critical path has no third-party surface.
    """
    kept: list[str] = []
    keep_current = False
    for raw in src.read_text(encoding="utf-8").splitlines():
        stripped = raw.rstrip("\n")
        is_indented = stripped[:1] in (" ", "\t")
        if not is_indented and stripped.strip():
            # a new top-level key (or a comment / document marker)
            if stripped.lstrip().startswith("#") or stripped.strip() in ("---", "..."):
                keep_current = False
                continue
            key = stripped.split(":", 1)[0].strip()
            keep_current = key in STAGED_YAML_KEYS
            if keep_current:
                kept.append(stripped)
        else:
            # blank line or indented continuation of the current key
            if keep_current and stripped.strip():
                kept.append(stripped)
    dest.write_text("\n".join(kept) + "\n", encoding="utf-8")


def copy_tree_verbatim(src: Path, dest: Path) -> None:
    shutil.copytree(src, dest, symlinks=False)


def stage(bundle: Path, provider_root: Path, meta: Path, canary: bool) -> int:
    if not bundle.is_dir():
        print(f"STAGE-FAIL: bundle not found: {bundle}", file=sys.stderr)
        return 2
    if provider_root.exists():
        shutil.rmtree(provider_root)
    provider_root.mkdir(parents=True)
    meta.mkdir(parents=True, exist_ok=True)

    for name in ALLOWED_TOP_LEVEL:
        src = bundle / name
        if not src.exists():
            continue
        try:
            _assert_no_reparse(src)
        except _StageError as exc:
            print(f"STAGE-FAIL: sentinel: {exc}", file=sys.stderr)
            return 5
        dest = provider_root / name
        if name == "scenario.yaml":
            sanitize_scenario_yaml(src, dest)
        elif src.is_dir():
            copy_tree_verbatim(src, dest)
        else:
            shutil.copy2(src, dest)

    # Required-input assertions (structural sentinel, part 1).
    if not (provider_root / "inputs").is_dir():
        print("STAGE-FAIL: sentinel: inputs/ missing from provider root", file=sys.stderr)
        return 3
    if not (provider_root / "scenario.yaml").is_file():
        print("STAGE-FAIL: sentinel: scenario.yaml missing from provider root", file=sys.stderr)
        return 3

    decoy_rel = None
    if canary:
        # Plant a honeypot answer key with a nonce + plausible-but-WRONG values. The scorer greps the
        # candidate output + transcript for the nonce/decoy; a hit proves the candidate read the oracle.
        nonce = uuid.uuid4().hex
        decoy = {
            "_canary_nonce": nonce,
            "selected_option": "Option A - the deliberately wrong decoy answer",
            "decoy_values": [f"CANARY-{nonce[:8]}-WRONG"],
        }
        oracle_dir = provider_root / "oracle"
        oracle_dir.mkdir(exist_ok=True)
        decoy_rel = "oracle/answer-key.json"
        (oracle_dir / "answer-key.json").write_text(json.dumps(decoy, indent=2), encoding="utf-8")
        (meta / "canary.json").write_text(
            json.dumps({"nonce": nonce, "decoy_values": decoy["decoy_values"], "decoy_path": decoy_rel}, indent=2),
            encoding="utf-8",
        )

    # Structural sentinel, part 2: no oracle/verifier/discrimination path in the provider root
    # (except the single known decoy in canary mode).
    manifest = []
    for p in sorted(provider_root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(provider_root).as_posix()
        if rel == decoy_rel:
            manifest.append({"path": rel, "sha256": sha256_file(p), "canary_decoy": True})
            continue
        segments = rel.split("/")
        if any(seg in FORBIDDEN_SEGMENTS for seg in segments[:-1]) or segments[-1] in FORBIDDEN_FILES:
            print(f"STAGE-FAIL: sentinel: forbidden path reached provider root: {rel}", file=sys.stderr)
            return 4
        manifest.append({"path": rel, "sha256": sha256_file(p)})

    (meta / "staging-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"STAGE-OK: {len(manifest)} files staged to {provider_root}"
          + (" [canary]" if canary else ""))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Stage a bundle into an oracle-free provider-visible root.")
    ap.add_argument("--bundle", type=Path, required=True)
    ap.add_argument("--provider-root", type=Path, required=True)
    ap.add_argument("--meta", type=Path, required=True)
    ap.add_argument("--sentinel-canary", action="store_true", help="plant a decoy answer key (harness-validation only)")
    args = ap.parse_args(argv)
    return stage(args.bundle, args.provider_root, args.meta, args.sentinel_canary)


if __name__ == "__main__":
    raise SystemExit(main())
