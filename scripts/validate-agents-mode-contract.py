#!/usr/bin/env python3
"""Validate the shared agents-mode contract against docs and pack surfaces."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any, Callable


PRESET_DOCS = Path("docs/agents-mode-reference.md")
INIT_SURFACES = {
    "codex": Path("src.codex/skills/init-project/SKILL.md"),
    "claude": Path("src.claude/commands/agents-init-project.md"),
    "gemini": Path("src.gemini/skills/init-project/SKILL.md"),
    "qwen": Path("src.qwen/skills/init-project/SKILL.md"),
}


class ContractError(Exception):
    """Raised when the agents-mode contract drifts."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContractError(f"missing {path}") from exc
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ContractError(f"{path} must contain a JSON object")
    return data


def parse_markdown_tables(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    tables: list[dict[str, Any]] = []
    current: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("|") and line.endswith("|"):
            current.append(line)
            continue
        if current:
            tables.append(parse_markdown_table(current, path))
            current = []
    if current:
        tables.append(parse_markdown_table(current, path))

    return tables


def parse_markdown_table(lines: list[str], path: Path) -> dict[str, Any]:
    if len(lines) < 2:
        raise ContractError(f"malformed Markdown table in {path}")

    rows = [split_markdown_row(line) for line in lines]
    header = rows[0]
    body = rows[2:] if is_separator_row(rows[1]) else rows[1:]
    width = len(header)
    normalized_body = []
    for row in body:
        if len(row) != width:
            raise ContractError(
                f"broken Markdown table pipe count in {path}: {row!r}"
            )
        normalized_body.append(row)
    return {"header": header, "rows": normalized_body}


def split_markdown_row(line: str) -> list[str]:
    content = line.strip()
    if content.startswith("|"):
        content = content[1:]
    if content.endswith("|"):
        content = content[:-1]

    cells: list[str] = []
    current: list[str] = []
    in_code = False
    for char in content:
        if char == "`":
            in_code = not in_code
            current.append(char)
            continue
        if char == "|" and not in_code:
            cells.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    cells.append("".join(current).strip())
    return cells


def is_separator_row(row: list[str]) -> bool:
    return all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in row)


def find_table(
    path: Path,
    required_headers: list[str],
    first_header: str | None = None,
) -> dict[str, Any]:
    for table in parse_markdown_tables(path):
        header = table["header"]
        if first_header is not None and (not header or header[0] != first_header):
            continue
        if all(required in header for required in required_headers):
            return table
    raise ContractError(
        f"missing Markdown table in {path} with headers: {required_headers}"
    )


def table_rows_by_first_cell(table: dict[str, Any], path: Path) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for row in table["rows"]:
        first = row[0]
        if first in result:
            raise ContractError(f"duplicate table row {first!r} in {path}")
        result[first] = row
    return result


def code(value: str) -> str:
    return f"`{value}`"


def reference_count_cell(mode: str) -> str:
    if mode == "all-1":
        return "all `1`"
    if mode == "advisory-review-2":
        return "advisory+review `2`, others `1`"
    raise ContractError(f"unknown opinion-count preset mode: {mode}")


def init_count_cell(mode: str) -> str:
    if mode == "all-1":
        return "all `1`"
    if mode == "advisory-review-2":
        return "advisory+review lanes `2`, others `1`"
    raise ContractError(f"unknown opinion-count preset mode: {mode}")


def workdir_cell(value: str) -> str:
    return f"all `{value}`"


def row_values(
    presets: dict[str, Any],
    preset_order: list[str],
    key: str,
    *,
    reference: bool = False,
) -> list[str]:
    cells = []
    for preset in preset_order:
        value = presets[preset]["expansion"][key]
        if key == "externalOpinionCounts":
            cells.append(reference_count_cell(value) if reference else init_count_cell(value))
        elif key == "externalPriorityProfiles":
            cells.append("shipped as-is")
        else:
            cells.append(code(value))
    return cells


def check_table_row(
    rows: dict[str, list[str]],
    label: str,
    expected_values: list[str],
    path: Path,
) -> None:
    row = rows.get(label)
    if row is None:
        raise ContractError(f"{path} missing row {label!r}")
    actual = row[1:]
    if actual != expected_values:
        raise ContractError(
            f"{path} row {label!r} drifted:\n"
            f"  expected: {expected_values}\n"
            f"  actual:   {actual}"
        )


def validate_available_presets(
    root: Path,
    presets_data: dict[str, Any],
) -> None:
    path = root / PRESET_DOCS
    table = find_table(
        path,
        ["Preset", "Role", "When to use"],
        first_header="Preset",
    )
    rows = table_rows_by_first_cell(table, path)
    for preset in presets_data["presetOrder"]:
        data = presets_data["presets"][preset]
        label = code(preset)
        expected = [label, data["role"], data["whenToUse"]]
        actual = rows.get(label)
        if actual != expected:
            raise ContractError(
                f"{path} available preset row {preset!r} drifted:\n"
                f"  expected: {expected}\n"
                f"  actual:   {actual}"
            )


def validate_reference_expansion(root: Path, presets_data: dict[str, Any]) -> None:
    path = root / PRESET_DOCS
    preset_order = presets_data["presetOrder"]
    presets = presets_data["presets"]
    required_headers = ["Key"] + [code(preset) for preset in preset_order]
    table = find_table(path, required_headers, first_header="Key")
    rows = table_rows_by_first_cell(table, path)

    for key in [
        "consultantMode",
        "delegationMode",
        "parallelMode",
        "mcpMode",
        "preferExternalWorker",
        "preferExternalReviewer",
        "externalProvider",
        "externalPriorityProfile",
        "reserveResolver",
    ]:
        check_table_row(rows, code(key), row_values(presets, preset_order, key), path)

    check_table_row(
        rows,
        code("externalOpinionCounts"),
        row_values(presets, preset_order, "externalOpinionCounts", reference=True),
        path,
    )
    check_table_row(
        rows,
        "workdir modes",
        [
            workdir_cell(presets[preset]["expansion"]["externalCodexWorkdirMode"])
            for preset in preset_order
        ],
        path,
    )
    check_table_row(
        rows,
        code("externalModelMode"),
        row_values(presets, preset_order, "externalModelMode"),
        path,
    )
    check_table_row(
        rows,
        code("externalCodexProfile"),
        row_values(presets, preset_order, "externalCodexProfile"),
        path,
    )
    check_table_row(
        rows,
        "`externalClaudeProfile` (Codex-line only)",
        row_values(presets, preset_order, "externalClaudeProfile"),
        path,
    )


def validate_init_expansion(
    root: Path,
    presets_data: dict[str, Any],
    provider: str,
    path: Path,
) -> None:
    full_path = root / path
    preset_order = presets_data["presetOrder"]
    presets = presets_data["presets"]
    required_headers = ["Key"] + [
        f"`{preset}` ({role_from_preset_name(preset, presets[preset]['role'])})"
        for preset in preset_order
    ]
    table = find_table(full_path, required_headers, first_header="Key")
    rows = table_rows_by_first_cell(table, full_path)

    for key in [
        "consultantMode",
        "delegationMode",
        "parallelMode",
        "mcpMode",
        "preferExternalWorker",
        "preferExternalReviewer",
        "externalProvider",
        "externalPriorityProfile",
        "reserveResolver",
        "externalPriorityProfiles",
        "externalOpinionCounts",
        "externalCodexWorkdirMode",
        "externalClaudeWorkdirMode",
        "externalModelMode",
        "externalCodexProfile",
    ]:
        check_table_row(rows, code(key), row_values(presets, preset_order, key), full_path)

    claude_profile_row = rows.get(code("externalClaudeProfile"))
    if provider == "codex":
        check_table_row(
            rows,
            code("externalClaudeProfile"),
            row_values(presets, preset_order, "externalClaudeProfile"),
            full_path,
        )
    elif claude_profile_row is not None:
        raise ContractError(
            f"{full_path} must not expose Codex-only externalClaudeProfile row"
        )


def validate_init_canonical_shape(
    root: Path,
    schema_data: dict[str, Any],
    provider: str,
    path: Path,
) -> None:
    full_path = root / path
    yaml_lines = extract_canonical_yaml_shape(full_path)
    actual_keys = top_level_yaml_keys(yaml_lines)
    expected_keys = expected_canonical_shape_keys(schema_data, provider)
    if actual_keys != expected_keys:
        raise ContractError(
            f"{full_path} canonical shape keys drifted:\n"
            f"  expected: {expected_keys}\n"
            f"  actual:   {actual_keys}"
        )

    profiles_block = yaml_block_for_key(yaml_lines, "externalPriorityProfiles")
    if len(profiles_block) > 1:
        actual_profiles = parse_yaml_profile_block(profiles_block)
        if actual_profiles != schema_data["priorityProfiles"]:
            raise ContractError(
                f"{full_path} canonical shape externalPriorityProfiles drifted"
            )

    counts_block = yaml_block_for_key(yaml_lines, "externalOpinionCounts")
    if len(counts_block) > 1:
        actual_counts = parse_yaml_count_block(counts_block)
        expected_counts = {
            lane: int(value)
            for lane, value in schema_data["externalOpinionCounts"].items()
        }
        if actual_counts != expected_counts:
            raise ContractError(
                f"{full_path} canonical shape externalOpinionCounts drifted"
            )


def expected_canonical_shape_keys(
    schema_data: dict[str, Any],
    provider: str,
) -> list[str]:
    keys: list[str] = []
    for scalar in schema_data["scalarKeys"]:
        providers = scalar.get("providers")
        if providers and provider not in providers:
            continue
        name = scalar["name"]
        keys.append(name)
        if name == "reserveResolver":
            keys.extend(["externalPriorityProfiles", "externalOpinionCounts"])
    return keys


def extract_canonical_yaml_shape(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    marker_index = None
    for index, line in enumerate(lines):
        if "Use this canonical" in line:
            marker_index = index
            break
    if marker_index is None:
        raise ContractError(f"{path} missing canonical shape marker")

    start = None
    for index in range(marker_index + 1, len(lines)):
        if lines[index].strip() == "```yaml":
            start = index + 1
            break
    if start is None:
        raise ContractError(f"{path} missing canonical shape YAML block")

    for index in range(start, len(lines)):
        if lines[index].strip() == "```":
            block = "\n".join(lines[start:index])
            return textwrap.dedent(block).splitlines()
    raise ContractError(f"{path} canonical shape YAML block is unterminated")


def top_level_yaml_keys(lines: list[str]) -> list[str]:
    keys: list[str] = []
    for line in lines:
        if line.startswith(" ") or not line.strip():
            continue
        match = re.match(r"^([A-Za-z][A-Za-z0-9]*):", line)
        if match:
            keys.append(match.group(1))
    return keys


def yaml_block_for_key(lines: list[str], key: str) -> list[str]:
    start = None
    for index, line in enumerate(lines):
        if line.startswith(f"{key}:"):
            start = index
            break
    if start is None:
        raise ContractError(f"canonical shape missing {key}")

    result = [lines[start]]
    for line in lines[start + 1 :]:
        if line and not line.startswith(" "):
            break
        result.append(line)
    return result


def parse_yaml_profile_block(lines: list[str]) -> dict[str, dict[str, list[str]]]:
    profiles: dict[str, dict[str, list[str]]] = {}
    current_profile: str | None = None
    profile_re = re.compile(r"^ {2}([^:#][^:]*):")
    lane_re = re.compile(r"^ {4}([^:#][^:]*):\s*\[([^]]*)\]")
    for line in lines[1:]:
        profile_match = profile_re.match(line)
        if profile_match and not line.startswith("    "):
            current_profile = profile_match.group(1).strip()
            profiles[current_profile] = {}
            continue
        lane_match = lane_re.match(line)
        if lane_match and current_profile:
            providers = [
                provider.strip()
                for provider in lane_match.group(2).split(",")
                if provider.strip()
            ]
            profiles[current_profile][lane_match.group(1).strip()] = providers
    return profiles


def parse_yaml_count_block(lines: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    count_re = re.compile(r"^ {2}([^:#][^:]*):\s*([0-9]+)")
    for line in lines[1:]:
        count_match = count_re.match(line)
        if count_match:
            counts[count_match.group(1).strip()] = int(count_match.group(2))
    return counts


def validate_raised_count_bullets(
    root: Path,
    presets_data: dict[str, Any],
    path: Path,
) -> None:
    full_path = root / path
    text = full_path.read_text(encoding="utf-8")
    marker = "`correctness-first` and `power-mode` lane-specific opinion counts:"
    if marker not in text:
        raise ContractError(f"{full_path} missing raised opinion-count list")
    for lane in presets_data["raisedOpinionCountLanes"]:
        expected = f"- `{lane}: 2`"
        if expected not in text:
            raise ContractError(
                f"{full_path} raised opinion-count list missing {expected!r}"
            )
    if "- all other lanes: `1`" not in text:
        raise ContractError(
            f"{full_path} raised opinion-count list missing all-other-lanes rule"
        )


def validate_generated_docs_sync(root: Path) -> None:
    script = root / "scripts" / "sync-agents-mode-docs.py"
    if not script.is_file():
        raise ContractError(f"missing {script}")
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--root",
            str(root),
            "--check",
        ],
        cwd=root,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise ContractError(
            "generated agents-mode docs are out of sync:\n"
            f"{result.stdout}{result.stderr}"
        )


def role_from_preset_name(preset: str, role: str) -> str:
    # The init tables use compact column labels that intentionally differ from
    # the operator-facing role wording for a few presets.
    overrides = {
        "default": "safe-init",
        "absolute-balance": "everyday center",
        "external-aggressive": "aggressive external use",
        "correctness-first": "no-time-limit correctness",
        "power-mode": "hardest-task maximum result",
        "max-speed": "speed-first",
    }
    return overrides.get(preset, role)


def parse_defaults(path: Path) -> dict[str, Any]:
    scalars: dict[str, str] = {}
    profiles: dict[str, dict[str, list[str]]] = {}
    counts: dict[str, int] = {}
    current_block: str | None = None
    current_profile: str | None = None

    top_key_re = re.compile(r"^([A-Za-z][A-Za-z0-9]*):(?:\s*(.*))?$")
    profile_re = re.compile(r"^ {2}([^:#][^:]*):")
    lane_re = re.compile(r"^ {4}([^:#][^:]*):\s*\[([^]]*)\]")
    count_re = re.compile(r"^ {2}([^:#][^:]*):\s*([0-9]+)")

    for line in path.read_text(encoding="utf-8").splitlines():
        top_match = top_key_re.match(line)
        if top_match and not line.startswith(" "):
            key = top_match.group(1)
            rest = top_match.group(2) or ""
            current_block = key
            current_profile = None
            if key not in {"externalPriorityProfiles", "externalOpinionCounts"}:
                scalars[key] = strip_comment(rest)
            continue

        if current_block == "externalPriorityProfiles":
            profile_match = profile_re.match(line)
            if profile_match and not line.startswith("    "):
                current_profile = profile_match.group(1).strip()
                profiles[current_profile] = {}
                continue
            lane_match = lane_re.match(line)
            if lane_match and current_profile:
                lane = lane_match.group(1).strip()
                providers = [
                    provider.strip()
                    for provider in lane_match.group(2).split(",")
                    if provider.strip()
                ]
                profiles[current_profile][lane] = providers
                continue

        if current_block == "externalOpinionCounts":
            count_match = count_re.match(line)
            if count_match:
                counts[count_match.group(1).strip()] = int(count_match.group(2))

    return {"scalars": scalars, "profiles": profiles, "counts": counts}


def strip_comment(value: str) -> str:
    return value.split(" #", 1)[0].strip()


def validate_defaults(root: Path, schema_data: dict[str, Any]) -> None:
    defaults_path = root / "shared" / "agents-mode.defaults.yaml"
    defaults = parse_defaults(defaults_path)
    scalars = defaults["scalars"]

    for key_data in schema_data["scalarKeys"]:
        if key_data.get("providers") == ["codex"]:
            continue
        key = key_data["name"]
        actual = scalars.get(key)
        expected = key_data["default"]
        if actual != expected:
            raise ContractError(
                f"{defaults_path} scalar {key!r} default drifted: "
                f"expected {expected!r}, got {actual!r}"
            )

    expected_profiles = schema_data["priorityProfiles"]
    if defaults["profiles"] != expected_profiles:
        raise ContractError(
            f"{defaults_path} externalPriorityProfiles drifted from schema"
        )

    expected_counts = {
        lane: int(value)
        for lane, value in schema_data["externalOpinionCounts"].items()
    }
    if defaults["counts"] != expected_counts:
        raise ContractError(
            f"{defaults_path} externalOpinionCounts drifted from schema"
        )


def validate_manual_reference_surfaces(root: Path) -> None:
    reference = (root / "docs" / "agents-mode-reference.md").read_text(
        encoding="utf-8"
    )
    external_worker = (root / "docs" / "external-worker-design.md").read_text(
        encoding="utf-8"
    )
    candidates = [
        root / "docs" / "agents-mode-reference.md",
        root / "docs" / "external-worker-design.md",
        root / "RELEASE_NOTES.md",
        root / "src.codex" / "skills" / "consultant" / "SKILL.md",
        root / "src.codex" / "skills" / "lead" / "external-dispatch.md",
        root / "src.codex" / "skills" / "lead" / "subagent-contracts.md",
        root / "src.claude" / "agents" / "consultant.md",
        root / "src.gemini" / "skills" / "lead" / "external-dispatch.md",
        root / "src.gemini" / "skills" / "lead" / "subagent-contracts.md",
        root / "src.qwen" / "skills" / "lead" / "subagent-contracts.md",
    ]

    if "| Gemini CLI | `disabled` | `auto` | `auto`" not in reference:
        raise ContractError(
            "agents-mode reference must keep Gemini first-write defaults on shared auto defaults"
        )
    if "| Qwen Code | `disabled` | `auto` | `auto`" not in reference:
        raise ContractError(
            "agents-mode reference must keep Qwen first-write defaults on shared auto defaults"
        )
    if "explicit `gemini` only" in reference or "explicit `qwen` only" in reference:
        raise ContractError(
            "agents-mode reference must not present example providers as first-write defaults"
        )

    if "externalPriorityProfile: balanced | quality-first | <custom>" not in external_worker:
        raise ContractError(
            "external-worker design must document quality-first as a shipped priority profile"
        )
    external_worker_lines = set(external_worker.splitlines())
    for lane in [
        "review.performance-architecture",
        "review.ui-visual-correctness",
    ]:
        if f"     {lane}: 1" not in external_worker_lines:
            raise ContractError(
                f"external-worker design YAML example misindents {lane}"
            )
        if f"   {lane}: 1" in external_worker_lines or f"      {lane}: 1" in external_worker_lines:
            raise ContractError(
                f"external-worker design YAML example has top-level {lane}"
            )

    for path in candidates:
        text = path.read_text(encoding="utf-8")
        if "--reasoning-effort" in text or re.search(
            r"(?:--model\s+)?gpt-5\.[0-9]+\s+--reasoning-effort\s+xhigh",
            text,
        ):
            raise ContractError(
                f"{path.relative_to(root)} documents unsupported Codex reasoning CLI flag"
            )


# Enum-copy drift guards. The externalCodexProfile guard exists because model-enum
# copies drift (the recurring drift: gpt-5.3-codex-spark was missing from ~9 copies
# until 2026-07-07); the externalClaudeProfile sibling exists because the same
# drift class recurred Claude-side with zero guard (the Claude vocabulary sat
# frozen at the opus/sonnet family through three Codex migrations). Detection is
# derived from the SCHEMA at runtime — BOTH the value list AND the token SHAPE.
# The first cut hardcoded the `gpt-5.\d+-` namespace, so the guard would have
# silently no-oped at exactly the moment a family rename swept the copies; the
# shape is now generalized from whatever values the schema carries.
_ENUM_SCAN_ROOTS = ("docs", "shared", "src.claude", "src.codex", "src.gemini", "src.qwen")
_ENUM_SCAN_TOP = ("README.md", "INSTALL.md")
_ENUM_SCAN_EXTS = (".md", ".json", ".yaml", ".yml", ".toml", ".sh", ".ps1")
# Changelog / release-note / history stems are EXEMPT: recording a superseded
# enum ("was default | gpt-5.6-sol-xhigh | gpt-5.6-luna") is the point there, exactly
# as the C6 stale-relation-residue hook exempts the same stems. A live-surface
# enum validator must not guard historical prose.
_ENUM_EXEMPT_STEMS = {
    "release_notes", "release-notes", "changelog", "changes", "history", "news",
}


def _schema_allowed_values(schema_data: dict[str, Any], key_name: str) -> set[str]:
    for entry in schema_data.get("scalarKeys", []):
        if isinstance(entry, dict) and entry.get("name") == key_name:
            allowed = set(entry.get("allowed", []))
            if allowed:
                return allowed
            break
    raise ContractError(f"schema has no {key_name}.allowed to validate against")


def _enum_token_regex(allowed: set[str]) -> str:
    """Token-shape regex text DERIVED from the schema values, never hardcoded.

    Two alternation tiers:
    - each allowed value verbatim (covers shape-less values such as `default`);
    - a generalized family shape per hyphenated value: the leading name segment
      is kept, the version/tier tail is generalized (`gpt-5.6-sol-xhigh` ->
      `gpt-<segments>`, `opus-xhigh` -> `opus-<segments>`), so a STALE copy from
      an earlier generation of the same family (e.g. `gpt-5.5-fast` during a
      gpt-5.6 migration) is still recognized as an enum token and fails the
      exact-set check instead of escaping detection entirely.
    A future family jump re-derives the shape from the new schema values, so the
    guard cannot silently no-op the way the hardcoded `gpt-5.\\d+-` namespace
    would have. Both tiers are boundary-guarded so prose like `runtime-default`
    or `claude-sonnet` never yields a spurious token.
    """
    segment = r"[a-z0-9]+(?:\.[0-9]+)*"
    literals: set[str] = set()
    shapes: set[str] = set()
    for value in allowed:
        literals.add(re.escape(value))
        family = re.match(r"^([a-z]+)-", value)
        if family:
            shapes.add(rf"{re.escape(family.group(1))}(?:-{segment})+")
    parts = sorted(shapes) + sorted(literals, key=len, reverse=True)
    return rf"(?<![A-Za-z0-9-])(?:{'|'.join(parts)})(?![A-Za-z0-9])"


def _iter_enum_scan_files(root: Path) -> list[Path]:
    files: list[Path] = [root / name for name in _ENUM_SCAN_TOP]
    for sub in _ENUM_SCAN_ROOTS:
        d = root / sub
        if d.is_dir():
            files.extend(
                p for p in d.rglob("*")
                if p.is_file() and p.suffix in _ENUM_SCAN_EXTS
                and "/.scratch/" not in p.as_posix()
            )
    return files


def _validate_profile_enum_copies(
    root: Path,
    schema_data: dict[str, Any],
    key_name: str,
    *,
    line_anchor: str | None = None,
    path_filter: Callable[[Path], bool] | None = None,
) -> None:
    """Every LIVE surface that ENUMERATES the profile-enum allowed values
    (an `X | Y | Z` listing) must carry EXACTLY the schema set — the schema
    (shared/agents-mode.schema.json) is the single owner. Fail-closed on BOTH a
    missing value AND an extra/renamed value (a schema rename must sweep every
    copy).

    Design (hardening the first cut after the 2026-07-07 acceptance commission):
    - detection is DERIVED from the schema values — value list AND token shape —
      so neither a dropped anchor token nor a family rename can defeat the scan;
    - surfaces are DISCOVERED by globbing the doc/config trees (a new enumerating
      file is auto-covered) — but changelog/release-note/history stems are EXEMPT
      (recording a superseded enum there is legitimate, mirroring the C6 hook);
    - a markdown PRESET-TABLE row (starts with `|`, scatters the tokens across
      cells) is skipped, so it is not a false positive;
    - the check is EXACT set-equality on a listing line, so a removed/renamed
      schema value fails closed (not merely a subset check)."""
    allowed = _schema_allowed_values(schema_data, key_name)
    token_regex = _enum_token_regex(allowed)
    token_re = re.compile(token_regex)
    listing_re = re.compile(rf"(?:{token_regex})\s*\|\s*(?:{token_regex})")

    for path in _iter_enum_scan_files(root):
        if path.stem.lower() in _ENUM_EXEMPT_STEMS:
            continue  # changelog / release-note / history — historical prose
        if path_filter is not None and not path_filter(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("|"):
                continue  # markdown preset-table row, not an inline enum listing
            if line_anchor is not None and line_anchor not in line:
                continue
            if not listing_re.search(line):
                continue
            found = set(token_re.findall(line))
            if found != allowed:
                rel = path.relative_to(root).as_posix()
                missing = sorted(allowed - found)
                extra = sorted(found - allowed)
                detail = []
                if missing:
                    detail.append(f"missing {missing}")
                if extra:
                    detail.append(f"unknown/removed {extra}")
                raise ContractError(
                    f"{rel}:{lineno} {key_name} enum listing "
                    f"{'; '.join(detail)} — must equal the schema set "
                    f"{sorted(allowed)} (owner: shared/agents-mode.schema.json)"
                )


def validate_codex_profile_enum(root: Path, schema_data: dict[str, Any]) -> None:
    """externalCodexProfile enum-copy drift guard (see _validate_profile_enum_copies)."""
    _validate_profile_enum_copies(root, schema_data, "externalCodexProfile")


def validate_claude_profile_enum(root: Path, schema_data: dict[str, Any]) -> None:
    """externalClaudeProfile enum-copy drift guard — the Claude mirror of the
    Codex guard (see _validate_profile_enum_copies). Added when the Claude
    vocabulary migrated to the fable family: the Codex enum went through three
    migrations under a guard while the Claude enum copies had none."""
    _validate_profile_enum_copies(root, schema_data, "externalClaudeProfile")


def validate_external_provider_enum(root: Path, schema_data: dict[str, Any]) -> None:
    """Keep scalar ``externalProvider`` enum listings schema-exact.

    Provider-priority examples intentionally list only the candidates legal in
    their particular lane; they are validated by ``validate_schema``.  Only a
    line that names the scalar can be an allowed-value enum copy.
    """
    active_roots = {"docs", "shared", "src.codex", "src.claude"}
    active_root_files = {"AGENTS.md", "CLAUDE.md", "README.md", "INSTALL.md"}

    def active_surface(path: Path) -> bool:
        relative = path.relative_to(root)
        return (
            relative.name in active_root_files and len(relative.parts) == 1
        ) or relative.parts[0] in active_roots

    _validate_profile_enum_copies(
        root,
        schema_data,
        "externalProvider",
        line_anchor="externalProvider",
        path_filter=active_surface,
    )


def validate_schema(schema_data: dict[str, Any], presets_data: dict[str, Any]) -> None:
    production = set(schema_data["productionAutoProviders"])
    examples = set(schema_data["exampleOnlyProviders"])
    explicit = set(schema_data["explicitOnlyProviders"])
    supplemental = set(schema_data["advisoryReviewSupplementalProviders"])
    buckets = (production, examples, explicit, supplemental)
    if any(
        left & right
        for index, left in enumerate(buckets)
        for right in buckets[index + 1 :]
    ):
        raise ContractError("provider classification buckets overlap")
    provider_allowed = _schema_allowed_values(schema_data, "externalProvider")
    if provider_allowed != {"auto"} | production | examples | explicit:
        raise ContractError("externalProvider enum and classification buckets drifted")

    lanes = set(schema_data["externalOpinionCounts"])
    for profile_name, lanes_map in schema_data["priorityProfiles"].items():
        for lane, providers in lanes_map.items():
            if lane not in lanes:
                raise ContractError(f"profile {profile_name} uses unknown lane {lane}")
            provider_set = set(providers)
            if provider_set & (examples | explicit):
                raise ContractError(
                    f"profile {profile_name} lane {lane} includes non-auto provider"
                )
            if "reserve" in provider_set:
                if not (lane.startswith("advisory.") or lane.startswith("review.")):
                    raise ContractError(f"profile {profile_name} lane {lane} uses reserve")
                if providers[-1] != "reserve":
                    raise ContractError(
                        f"profile {profile_name} lane {lane} must keep reserve last"
                    )
            if not provider_set <= production | supplemental:
                raise ContractError(
                    f"profile {profile_name} lane {lane} has unknown provider"
                )

    scalar_names = {item["name"] for item in schema_data["scalarKeys"]}
    for preset in presets_data["presetOrder"]:
        expansion = presets_data["presets"][preset]["expansion"]
        required_keys = {
            "externalPriorityProfiles",
            "externalOpinionCounts",
        } | scalar_names
        missing = required_keys - set(expansion)
        if missing:
            raise ContractError(f"preset {preset} missing keys: {sorted(missing)}")
        if expansion["externalPriorityProfiles"] != "shipped-as-is":
            raise ContractError(f"preset {preset} must keep shipped profiles")
        if expansion["externalOpinionCounts"] not in {
            "all-1",
            "advisory-review-2",
        }:
            raise ContractError(f"preset {preset} has invalid opinion-count mode")

    power_profile = presets_data["presets"]["power-mode"]["expansion"][
        "externalPriorityProfile"
    ]
    if power_profile != "quality-first":
        raise ContractError(
            "preset power-mode must use externalPriorityProfile quality-first"
        )

    for lane in presets_data["raisedOpinionCountLanes"]:
        if lane not in lanes:
            raise ContractError(f"raised opinion-count lane is unknown: {lane}")
        if not (lane.startswith("advisory.") or lane.startswith("review.")):
            raise ContractError(
                f"raised opinion-count lane must be advisory/review: {lane}"
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="repository root")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    errors: list[str] = []
    try:
        schema_data = load_json(root / "shared" / "agents-mode.schema.json")
        presets_data = load_json(root / "shared" / "agents-mode.presets.json")
        validate_schema(schema_data, presets_data)
        validate_generated_docs_sync(root)
        validate_defaults(root, schema_data)
        validate_manual_reference_surfaces(root)
        validate_external_provider_enum(root, schema_data)
        validate_codex_profile_enum(root, schema_data)
        validate_claude_profile_enum(root, schema_data)
        validate_available_presets(root, presets_data)
        validate_reference_expansion(root, presets_data)
        validate_raised_count_bullets(root, presets_data, PRESET_DOCS)
        for provider, path in INIT_SURFACES.items():
            validate_init_expansion(root, presets_data, provider, path)
            validate_init_canonical_shape(root, schema_data, provider, path)
            validate_raised_count_bullets(root, presets_data, path)
    except ContractError as exc:
        errors.append(str(exc))

    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1

    print("PASS: agents-mode contract validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
