#!/usr/bin/env python3
"""Build deterministic Stage 0 inventories for an immutable Git baseline.

The generator reads the requested Git object rather than the working tree, so a
baseline remains reproducible after later commits. It emits:

- capability-inventory.json: every tracked leaf path, content digest and surface;
- test-inventory.json: every tracked file under tests/ with an initial retention map;
- baseline-manifest.json: immutable commit/tree identity and output digests;
- summary.md: a human-readable compact baseline report.

Exit 0 means the requested write/check succeeded. Exit 1 in --check mode means
committed outputs drift from the deterministic rendering. Pure stdlib.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Mapping, Sequence

SCHEMA_VERSION = 1
DEFAULT_REPOSITORY = "applicate2628/Orchestrarium"
OUTPUT_NAMES = (
    "capability-inventory.json",
    "test-inventory.json",
    "baseline-manifest.json",
    "summary.md",
)


class InventoryError(RuntimeError):
    """Stable user-facing baseline inventory error."""


def _run_git(repo_root: Path, *args: str, text: bool = True) -> str | bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr if text else result.stderr.decode("utf-8", errors="replace")
        raise InventoryError(f"git {' '.join(args)} failed: {stderr.strip()}")
    return result.stdout


def _resolve_commit(repo_root: Path, ref: str) -> tuple[str, str]:
    commit = str(_run_git(repo_root, "rev-parse", "--verify", f"{ref}^{{commit}}")).strip()
    tree = str(_run_git(repo_root, "rev-parse", "--verify", f"{commit}^{{tree}}")).strip()
    return commit, tree


def _list_tree(repo_root: Path, commit: str) -> list[tuple[str, str, str, str, int | None]]:
    raw = bytes(
        _run_git(
            repo_root,
            "ls-tree",
            "-r",
            "-z",
            "--full-tree",
            "--long",
            commit,
            text=False,
        )
    )
    parsed: list[tuple[str, str, str, str, int | None]] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        try:
            metadata, raw_path = record.split(b"\t", 1)
            mode, object_type, object_id, size_text = metadata.decode("ascii").split(" ", 3)
            path = raw_path.decode("utf-8", errors="surrogateescape")
            size = None if size_text == "-" else int(size_text)
        except (ValueError, UnicodeError) as exc:
            raise InventoryError(f"cannot parse git ls-tree record: {record!r}") from exc
        parsed.append((path, mode, object_type, object_id, size))
    parsed.sort(key=lambda item: item[0])
    return parsed


def _read_objects(repo_root: Path, object_ids: Sequence[str]) -> Mapping[str, tuple[str, bytes]]:
    unique_ids = list(dict.fromkeys(object_ids))
    process = subprocess.Popen(
        ["git", "cat-file", "--batch"],
        cwd=repo_root,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None
    objects: dict[str, tuple[str, bytes]] = {}
    try:
        for object_id in unique_ids:
            process.stdin.write(object_id.encode("ascii") + b"\n")
            process.stdin.flush()
            header = process.stdout.readline()
            if not header:
                raise InventoryError("git cat-file ended before returning an object header")
            header_parts = header.rstrip(b"\n").split(b" ")
            if len(header_parts) == 2 and header_parts[1] == b"missing":
                raise InventoryError(f"git object missing: {object_id}")
            if len(header_parts) != 3:
                raise InventoryError(f"unexpected git cat-file header: {header!r}")
            returned_id, object_type, size_text = header_parts
            size = int(size_text)
            content = process.stdout.read(size)
            separator = process.stdout.read(1)
            if len(content) != size or separator != b"\n":
                raise InventoryError(f"truncated git cat-file response for {object_id}")
            returned = returned_id.decode("ascii")
            objects[returned] = (object_type.decode("ascii"), content)
        process.stdin.close()
        stderr = process.stderr.read().decode("utf-8", errors="replace")
        return_code = process.wait()
        if return_code != 0:
            raise InventoryError(f"git cat-file --batch failed: {stderr.strip()}")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
    return objects


def _surface_kinds(path_text: str) -> list[str]:
    path = PurePosixPath(path_text)
    lowered = path_text.lower()
    basename = path.name.lower()
    suffix = path.suffix.lower()
    surfaces: set[str] = set()

    if path_text in {"AGENTS.md", "CLAUDE.md"} or "agents.shared" in lowered:
        surfaces.add("governance")
    if path.parts and path.parts[0] == "shared":
        surfaces.add("shared-source")
    if path.parts and path.parts[0].startswith("src."):
        surfaces.add("provider-pack")
        surfaces.add(f"provider:{path.parts[0][4:]}")
    if "skills" in path.parts and basename == "skill.md":
        surfaces.add("skill")
    if "agents" in path.parts and suffix in {".md", ".toml", ".yaml", ".yml"}:
        surfaces.add("agent")
    if "commands" in path.parts:
        surfaces.add("command")
    if "hooks" in path.parts or "hook" in basename:
        surfaces.add("hook")
    if path.parts and path.parts[0] == "tests":
        surfaces.add("test")
    if path.parts and path.parts[0] == "scripts" or suffix in {".py", ".sh", ".ps1"}:
        surfaces.add("script")
    if basename.startswith("install") or "installer" in lowered:
        surfaces.add("installer")
    if suffix in {".json", ".yaml", ".yml", ".toml", ".ini"}:
        surfaces.add("configuration")
    if suffix == ".md" or path.parts and path.parts[0].startswith("references-"):
        surfaces.add("documentation")
    if any(token in lowered for token in ("work-item", "ledger", "lifecycle", "closure")):
        surfaces.add("lifecycle")
    if path_text == "RELEASE_NOTES.md":
        surfaces.add("release-log")
    if len(path.parts) == 1 and path.name.startswith("."):
        surfaces.add("repository-metadata")
    if not surfaces:
        surfaces.add("repository-content")
    return sorted(surfaces)


def _primary_surface(surfaces: Sequence[str]) -> str:
    precedence = (
        "test",
        "skill",
        "agent",
        "command",
        "hook",
        "installer",
        "lifecycle",
        "governance",
        "configuration",
        "script",
        "release-log",
        "documentation",
        "provider-pack",
        "shared-source",
        "repository-metadata",
        "repository-content",
    )
    surface_set = set(surfaces)
    for candidate in precedence:
        if candidate in surface_set:
            return candidate
    return surfaces[0]


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_outputs(repo_root: Path, repository: str, requested_ref: str) -> dict[str, bytes]:
    commit, tree = _resolve_commit(repo_root, requested_ref)
    raw_entries = _list_tree(repo_root, commit)
    object_map = _read_objects(repo_root, [entry[3] for entry in raw_entries])

    entries: list[dict[str, object]] = []
    for path, mode, object_type, object_id, listed_size in raw_entries:
        actual_type, content = object_map[object_id]
        if actual_type != object_type:
            raise InventoryError(
                f"git object type drift for {path}: ls-tree={object_type}, cat-file={actual_type}"
            )
        size = len(content)
        if listed_size is not None and listed_size != size:
            raise InventoryError(
                f"git object size drift for {path}: ls-tree={listed_size}, cat-file={size}"
            )
        surfaces = _surface_kinds(path)
        entries.append(
            {
                "contentSha256": _sha256_bytes(content),
                "gitObject": object_id,
                "mode": mode,
                "objectType": object_type,
                "path": path,
                "primarySurface": _primary_surface(surfaces),
                "reviewState": "baseline-captured",
                "sizeBytes": size,
                "surfaces": surfaces,
            }
        )

    surface_counts = Counter(
        surface for entry in entries for surface in entry["surfaces"]  # type: ignore[index]
    )
    inventory_payload = {
        "schemaVersion": SCHEMA_VERSION,
        "baseline": {
            "commitSha": commit,
            "repository": repository,
            "requestedRef": requested_ref,
            "treeSha": tree,
        },
        "entries": entries,
        "summary": {
            "surfaceCounts": dict(sorted(surface_counts.items())),
            "trackedLeafEntries": len(entries),
        },
    }
    inventory_without_digest = _canonical_json(inventory_payload).encode("utf-8")
    inventory_payload["inventorySha256"] = _sha256_bytes(inventory_without_digest)
    capability_bytes = _canonical_json(inventory_payload).encode("utf-8")

    test_entries = []
    for entry in entries:
        path = str(entry["path"])
        if not path.startswith("tests/"):
            continue
        test_entries.append(
            {
                "behavioralContractIds": [],
                "contentSha256": entry["contentSha256"],
                "disposition": "retainedAs",
                "gitObject": entry["gitObject"],
                "kind": "test-file" if PurePosixPath(path).name.startswith("test_") else "test-support",
                "path": path,
                "replacementTests": [],
                "reviewState": "baseline-captured",
                "sizeBytes": entry["sizeBytes"],
            }
        )
    test_payload = {
        "schemaVersion": SCHEMA_VERSION,
        "baseline": {
            "commitSha": commit,
            "repository": repository,
            "treeSha": tree,
        },
        "entries": test_entries,
        "summary": {
            "retainedAs": len(test_entries),
            "testFiles": sum(1 for entry in test_entries if entry["kind"] == "test-file"),
            "testSupportFiles": sum(
                1 for entry in test_entries if entry["kind"] == "test-support"
            ),
            "total": len(test_entries),
        },
    }
    test_without_digest = _canonical_json(test_payload).encode("utf-8")
    test_payload["inventorySha256"] = _sha256_bytes(test_without_digest)
    test_bytes = _canonical_json(test_payload).encode("utf-8")

    summary_lines = [
        "# Orchestrarium V1 Immutable Baseline",
        "",
        f"- Repository: `{repository}`",
        f"- Requested ref: `{requested_ref}`",
        f"- Commit: `{commit}`",
        f"- Tree: `{tree}`",
        f"- Tracked leaf entries: **{len(entries)}**",
        f"- Files under `tests/`: **{len(test_entries)}**",
        f"- Test modules (`test_*.py`): **{test_payload['summary']['testFiles']}**",
        "",
        "## Surface Counts",
        "",
        "| Surface | Count |",
        "|---|---:|",
    ]
    summary_lines.extend(
        f"| `{surface}` | {count} |" for surface, count in sorted(surface_counts.items())
    )
    summary_lines.extend(
        [
            "",
            "## Contract",
            "",
            "This baseline inventories the immutable Git tree without changing runtime behavior.",
            "Every tracked leaf entry appears exactly once in the capability inventory, and every",
            "tracked file under `tests/` has an initial `retainedAs` disposition. Later semantic",
            "classification and replacement mappings must extend these records rather than silently",
            "dropping paths or tests.",
            "",
        ]
    )
    summary_bytes = "\n".join(summary_lines).encode("utf-8")

    generated = {
        "capability-inventory.json": capability_bytes,
        "test-inventory.json": test_bytes,
        "summary.md": summary_bytes,
    }
    manifest_payload = {
        "schemaVersion": SCHEMA_VERSION,
        "baseline": {
            "commitSha": commit,
            "repository": repository,
            "requestedRef": requested_ref,
            "treeSha": tree,
        },
        "generator": {
            "command": "python scripts/baseline/build_inventory.py",
            "deterministic": True,
            "runtimeMutation": False,
        },
        "outputs": {
            name: {"sha256": _sha256_bytes(content), "sizeBytes": len(content)}
            for name, content in sorted(generated.items())
        },
        "status": "baseline-captured",
    }
    generated["baseline-manifest.json"] = _canonical_json(manifest_payload).encode("utf-8")
    return generated


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _check_outputs(output_dir: Path, expected: Mapping[str, bytes]) -> list[str]:
    drift: list[str] = []
    for name in OUTPUT_NAMES:
        path = output_dir / name
        if not path.is_file():
            drift.append(f"missing {path}")
            continue
        actual = path.read_bytes()
        if actual != expected[name]:
            drift.append(
                f"content {path}: expected sha256={_sha256_bytes(expected[name])}, "
                f"actual sha256={_sha256_bytes(actual)}"
            )
    return drift


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY)
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".scratch") / "orche-stage0" / "orchestrarium-v1",
    )
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    repo_root = args.repo_root.resolve()
    output_dir = args.output_dir
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir

    try:
        expected = build_outputs(repo_root, args.repository, args.ref)
        if args.check:
            drift = _check_outputs(output_dir, expected)
            if drift:
                for message in drift:
                    print(f"DRIFT: {message}", file=sys.stderr)
                return 1
            print(f"RESULT: PASS baseline-inventory check {output_dir}")
            return 0

        for name in OUTPUT_NAMES:
            _atomic_write(output_dir / name, expected[name])
        print(f"RESULT: PASS baseline-inventory write {output_dir}")
        return 0
    except (InventoryError, OSError, ValueError) as exc:
        print(f"RESULT: FAIL baseline-inventory: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
