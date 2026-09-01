#!/usr/bin/env python3
"""Import candidate output from the provider root into a scored `out/` tree through one gate.

Phase-0 harness item H3 / invariant I2 (BUILD-PLAN-v2.1). The candidate works in place inside the
provider-visible root (H2). Its edits cross to the scorer ONLY through this gate, which is the single
trusted boundary. The gate:

  * detects changed / new files by sha256 diff against the staging manifest (H2 before-state),
  * restricts imports to the scenario's allowed_change_surface (the scope guard becomes an import
    FILTER, not just a post-hoc verdict),
  * rejects path traversal, symlinks / junctions / any Windows reparse point, and NTFS alternate
    data streams (a candidate-planted reparse point could redirect a score-time overlay back onto
    the oracle),
  * enforces size / count caps,
  * warns (does not auto-reject) on literal `oracle/` / `verifiers/` references inside imported text
    — the hard guarantee is exec-root isolation (H9), this is defense-in-depth signal only.

Writes <metaDir>/import-manifest.json: one record per candidate-surface path with its disposition
(imported | rejected-<reason> | unchanged). Exit 0 even when files are rejected (rejection is data,
not a tool error); exit non-zero only on a usage / IO fault.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import stat
import sys
from pathlib import Path

PER_FILE_MAX_BYTES = 10 * 1024 * 1024
TOTAL_MAX_BYTES = 100 * 1024 * 1024
MAX_FILES = 500
_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def is_reparse_point(path: Path) -> bool:
    """True for a symlink, junction, mount point, or any other reparse point (do not follow)."""
    lst = path.lstat()
    if stat.S_ISLNK(lst.st_mode):
        return True
    attrs = getattr(lst, "st_file_attributes", 0)
    return bool(attrs & _REPARSE)


def gate_reason(provider_root: Path, path: Path, rel: str, surface: list[str]) -> str | None:
    """Return a rejection reason, or None if the file is importable."""
    # ADS: any component carrying an NTFS alternate-data-stream name.
    if ":" in rel:
        return "rejected-ads"
    # Reparse point on the file OR any parent segment inside the provider root.
    probe = provider_root
    for seg in rel.split("/"):
        probe = probe / seg
        try:
            if probe.exists() and is_reparse_point(probe):
                return "rejected-reparse-point"
        except OSError:
            return "rejected-stat-error"
    # Containment: the resolved real path must stay inside the provider root (blocks traversal and any
    # reparse that slipped the per-segment check).
    try:
        real = path.resolve(strict=True)
        if not real.is_relative_to(provider_root.resolve()):
            return "rejected-traversal"
    except (OSError, ValueError):
        return "rejected-unresolvable"
    # Allowed-change-surface filter.
    if not any(fnmatch.fnmatch(rel, pat) for pat in surface):
        return "rejected-out-of-surface"
    # Size cap.
    if path.stat().st_size > PER_FILE_MAX_BYTES:
        return "rejected-oversize"
    return None


def load_surface(provider_root: Path) -> list[str]:
    """Parse allowed_change_surface from the (sanitized) provider scenario.yaml — flat list subset."""
    scenario = provider_root / "scenario.yaml"
    surface: list[str] = []
    in_key = False
    for raw in scenario.read_text(encoding="utf-8").splitlines():
        if not raw[:1].isspace() and raw.strip():
            in_key = raw.split(":", 1)[0].strip() == "allowed_change_surface"
            continue
        if in_key:
            item = raw.strip()
            if item.startswith("-"):
                surface.append(item[1:].strip())
    return surface


def load_before(meta: Path) -> dict[str, str]:
    manifest = json.loads((meta / "staging-manifest.json").read_text(encoding="utf-8"))
    return {rec["path"]: rec["sha256"] for rec in manifest if not rec.get("canary_decoy")}


def content_scan_flag(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return "oracle/" in text or "verifiers/" in text


def import_output(provider_root: Path, out_root: Path, meta: Path) -> int:
    if not provider_root.is_dir():
        print(f"IMPORT-FAIL: provider root not found: {provider_root}", file=sys.stderr)
        return 2
    surface = load_surface(provider_root)
    before = load_before(meta)
    if out_root.exists():
        import shutil
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True)

    records = []
    imported_bytes = 0
    imported_count = 0
    # Only consider files inside candidate-surface directories, diffed against the before-state.
    for p in sorted(provider_root.rglob("*")):
        try:
            if not p.is_file():
                continue
        except OSError:
            # e.g. a broken reparse point — record and skip.
            rel = p.relative_to(provider_root).as_posix()
            records.append({"path": rel, "disposition": "rejected-stat-error"})
            continue
        rel = p.relative_to(provider_root).as_posix()
        try:
            digest = sha256_file(p)
        except OSError:
            records.append({"path": rel, "disposition": "rejected-read-error"})
            continue
        # Unchanged staged files (inputs, pristine candidate scaffold, etc.) are not candidate output;
        # the scorer already holds them pristine. Skip silently. Every NEW or CHANGED file — anywhere
        # under the provider root — is a candidate mutation and goes through the gate, so an
        # out-of-surface or must_not_touch edit is RECORDED, not silently dropped.
        if before.get(rel) == digest:
            continue
        reason = gate_reason(provider_root, p, rel, surface)
        if reason is not None:
            records.append({"path": rel, "sha256": digest, "disposition": reason})
            continue
        size = p.stat().st_size
        if imported_count + 1 > MAX_FILES or imported_bytes + size > TOTAL_MAX_BYTES:
            records.append({"path": rel, "sha256": digest, "disposition": "rejected-batch-cap"})
            continue
        dest = out_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(p.read_bytes())
        imported_bytes += size
        imported_count += 1
        rec = {"path": rel, "sha256": digest, "size": size, "disposition": "imported"}
        if content_scan_flag(p):
            rec["content_flag"] = "mentions-oracle-or-verifiers"
        records.append(rec)

    (meta / "import-manifest.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    rejected = sum(1 for r in records if r["disposition"].startswith("rejected-"))
    print(f"IMPORT-OK: {imported_count} imported, {rejected} rejected -> {out_root}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Gate candidate output from provider root into out/.")
    ap.add_argument("--provider-root", type=Path, required=True)
    ap.add_argument("--out", dest="out_root", type=Path, required=True)
    ap.add_argument("--meta", type=Path, required=True)
    args = ap.parse_args(argv)
    return import_output(args.provider_root, args.out_root, args.meta)


if __name__ == "__main__":
    raise SystemExit(main())
