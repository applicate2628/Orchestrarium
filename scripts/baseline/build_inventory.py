#!/usr/bin/env python3
"""Build deterministic Stage 0 inventories from an immutable Git commit.

Exit 0 writes or verifies the requested evidence. Exit 1 is reserved for
verified output drift in ``--check`` mode. Exit 2 means invalid input or an
operational/evidence-access failure. Only Python's standard library is used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Mapping, Sequence

SCHEMA_VERSION = 2
DEFAULT_REPOSITORY = "applicate2628/Orchestrarium"
SKILL_BODY_NORMALIZATION = "utf8-strict+lf+leading-yaml-frontmatter-stripped-v1"
OBJECT_ID = re.compile(r"[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?")
OUTPUT_NAMES = (
    "capability-inventory.json",
    "test-inventory.json",
    "baseline-manifest.json",
    "summary.md",
)


class InventoryError(RuntimeError):
    """Stable user-facing baseline-inventory error."""


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validate_git_executable(value: Path) -> Path:
    try:
        resolved = value.expanduser().resolve(strict=True)
    except OSError as exc:
        raise InventoryError(f"cannot resolve selected Git executable {value}: {exc}") from exc
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise InventoryError(f"selected Git executable is not executable: {resolved}")
    return resolved


def _run_git(
    git_executable: Path,
    repo_root: Path,
    *args: str,
    text: bool = True,
) -> str | bytes:
    try:
        result = subprocess.run(
            [os.fspath(git_executable), *args],
            cwd=repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=text,
            check=False,
        )
    except OSError as exc:
        raise InventoryError(
            f"cannot launch selected Git executable {git_executable}: {exc}"
        ) from exc
    if result.returncode != 0:
        stderr = result.stderr if text else result.stderr.decode("utf-8", errors="replace")
        raise InventoryError(f"git {' '.join(args)} failed: {stderr.strip()}")
    return result.stdout


def _resolve_commit(
    git_executable: Path, repo_root: Path, ref: str
) -> tuple[str, str]:
    commit = str(
        _run_git(git_executable, repo_root, "rev-parse", "--verify", f"{ref}^{{commit}}")
    ).strip()
    tree = str(
        _run_git(
            git_executable,
            repo_root,
            "rev-parse",
            "--verify",
            f"{commit}^{{tree}}",
        )
    ).strip()
    if not OBJECT_ID.fullmatch(commit) or not OBJECT_ID.fullmatch(tree):
        raise InventoryError("selected Git returned a non-object identifier")
    return commit.lower(), tree.lower()


def _list_tree(
    git_executable: Path, repo_root: Path, commit: str
) -> list[tuple[str, str, str, str, int | None]]:
    raw = bytes(
        _run_git(
            git_executable,
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
        parsed.append((path, mode, object_type, object_id.lower(), size))
    parsed.sort(key=lambda item: item[0])
    return parsed


def _read_objects(
    git_executable: Path,
    repo_root: Path,
    object_ids: Sequence[str],
) -> Mapping[str, tuple[str, bytes]]:
    unique_ids = list(dict.fromkeys(object_ids))
    try:
        process = subprocess.Popen(
            [os.fspath(git_executable), "cat-file", "--batch"],
            cwd=repo_root,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise InventoryError(f"cannot launch git cat-file --batch: {exc}") from exc
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
            try:
                size = int(size_text)
            except ValueError as exc:
                raise InventoryError(f"invalid git object size: {size_text!r}") from exc
            content = process.stdout.read(size)
            separator = process.stdout.read(1)
            if len(content) != size or separator != b"\n":
                raise InventoryError(f"truncated git cat-file response for {object_id}")
            returned = returned_id.decode("ascii").lower()
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
    if (path.parts and path.parts[0] == "scripts") or suffix in {".py", ".sh", ".ps1"}:
        surfaces.add("script")
    if basename.startswith("install") or "installer" in lowered:
        surfaces.add("installer")
    if suffix in {".json", ".yaml", ".yml", ".toml", ".ini"}:
        surfaces.add("configuration")
    if suffix == ".md" or (path.parts and path.parts[0].startswith("references-")):
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
        "command",
        "agent",
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


def _normalise_skill_body(path: str, content: bytes) -> bytes:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InventoryError(f"Skill file is not valid UTF-8: {path}: {exc}") from exc
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if text.startswith("---") and not text.startswith("---\n"):
        raise InventoryError(f"malformed leading YAML frontmatter delimiter: {path}")
    if text.startswith("---\n"):
        lines = text.splitlines(keepends=True)
        closing: int | None = None
        for index, line in enumerate(lines[1:], start=1):
            if line.rstrip("\n") == "---":
                closing = index
                break
        if closing is None:
            raise InventoryError(f"unterminated leading YAML frontmatter: {path}")
        text = "".join(lines[closing + 1 :])
    return text.encode("utf-8")


def _inventory_payload(
    *,
    commit: str,
    tree: str,
    repository: str,
    requested_ref: str,
    entries: list[dict[str, object]],
) -> dict[str, object]:
    surface_counts = Counter(
        surface for entry in entries for surface in entry["surfaces"]  # type: ignore[index]
    )
    payload: dict[str, object] = {
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
    payload["inventorySha256"] = _sha256_bytes(_canonical_json(payload).encode("utf-8"))
    return payload


def build_outputs(
    repo_root: Path,
    repository: str,
    requested_ref: str,
    git_executable: Path,
    *,
    generator_path: str,
    generator_blob_sha: str | None,
    generator_materialization: str,
    generator_source_path: str,
) -> dict[str, bytes]:
    commit, tree = _resolve_commit(git_executable, repo_root, requested_ref)
    raw_entries = _list_tree(git_executable, repo_root, commit)
    object_map = _read_objects(
        git_executable, repo_root, [entry[3] for entry in raw_entries]
    )
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
        record: dict[str, object] = {
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
        if "skill" in surfaces:
            body = _normalise_skill_body(path, content)
            record.update(
                {
                    "skillBodyNormalization": SKILL_BODY_NORMALIZATION,
                    "skillBodySha256": _sha256_bytes(body),
                    "skillBodySizeBytes": len(body),
                }
            )
        entries.append(record)

    capability_payload = _inventory_payload(
        commit=commit,
        tree=tree,
        repository=repository,
        requested_ref=requested_ref,
        entries=entries,
    )
    capability_bytes = _canonical_json(capability_payload).encode("utf-8")

    test_entries: list[dict[str, object]] = []
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
                "kind": (
                    "test-file"
                    if PurePosixPath(path).name.startswith("test_")
                    else "test-support"
                ),
                "path": path,
                "replacementTests": [],
                "reviewState": "baseline-captured",
                "sizeBytes": entry["sizeBytes"],
            }
        )
    test_payload: dict[str, object] = {
        "schemaVersion": SCHEMA_VERSION,
        "baseline": {
            "commitSha": commit,
            "repository": repository,
            "treeSha": tree,
        },
        "entries": test_entries,
        "summary": {
            "retainedAs": len(test_entries),
            "testFiles": sum(entry["kind"] == "test-file" for entry in test_entries),
            "testSupportFiles": sum(
                entry["kind"] == "test-support" for entry in test_entries
            ),
            "total": len(test_entries),
        },
    }
    test_payload["inventorySha256"] = _sha256_bytes(
        _canonical_json(test_payload).encode("utf-8")
    )
    test_bytes = _canonical_json(test_payload).encode("utf-8")

    surface_counts = capability_payload["summary"]  # type: ignore[index]
    assert isinstance(surface_counts, dict)
    counts = surface_counts["surfaceCounts"]
    assert isinstance(counts, dict)
    summary_lines = [
        "# Orchestrarium V1 Immutable Baseline",
        "",
        f"- Repository: `{repository}`",
        f"- Requested ref: `{requested_ref}`",
        f"- Commit: `{commit}`",
        f"- Tree: `{tree}`",
        f"- Tracked leaf entries: **{len(entries)}**",
        f"- Files under `tests/`: **{len(test_entries)}**",
        "",
        "## Surface Counts",
        "",
        "| Surface | Count |",
        "|---|---:|",
    ]
    summary_lines.extend(f"| `{key}` | {counts[key]} |" for key in sorted(counts))
    summary_lines.extend(
        [
            "",
            "## Contract",
            "",
            "The inventory is derived from immutable Git objects. Skill-body digests use strict",
            "UTF-8 decoding, line-feed normalization, and stripping of only a leading YAML",
            "frontmatter block. Generated evidence is local and is not committed.",
            "",
        ]
    )
    summary_bytes = "\n".join(summary_lines).encode("utf-8")

    if generator_blob_sha is not None and not OBJECT_ID.fullmatch(generator_blob_sha):
        raise InventoryError("generator blob SHA must be an exact 40- or 64-character object ID")
    generated = {
        "capability-inventory.json": capability_bytes,
        "test-inventory.json": test_bytes,
        "summary.md": summary_bytes,
    }
    generator_record: dict[str, object] = {
        "command": f"python {generator_path}",
        "deterministic": True,
        "materialization": generator_materialization,
        "path": generator_path,
        "runtimeMutation": False,
        "sourcePath": generator_source_path,
    }
    if generator_blob_sha is not None:
        generator_record["gitBlobSha"] = generator_blob_sha.lower()
    manifest_payload = {
        "schemaVersion": SCHEMA_VERSION,
        "baseline": capability_payload["baseline"],
        "generator": generator_record,
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
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
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
    parser.add_argument("--git-executable", type=Path, required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".scratch") / "orche-stage0" / "orchestrarium-v1",
    )
    parser.add_argument("--generator-path", default="scripts/baseline/build_inventory.py")
    parser.add_argument("--generator-blob-sha")
    parser.add_argument(
        "--generator-materialization", default="working-tree-development-copy"
    )
    parser.add_argument(
        "--generator-source-path", default="scripts/baseline/build_inventory.py"
    )
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = args.repo_root.resolve()
    output_dir = args.output_dir
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir
    try:
        git_executable = _validate_git_executable(args.git_executable)
        expected = build_outputs(
            repo_root,
            args.repository,
            args.ref,
            git_executable,
            generator_path=args.generator_path,
            generator_blob_sha=args.generator_blob_sha,
            generator_materialization=args.generator_materialization,
            generator_source_path=args.generator_source_path,
        )
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
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
