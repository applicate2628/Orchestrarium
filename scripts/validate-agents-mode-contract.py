#!/usr/bin/env python3
"""Validate the shared agents-mode contract against docs and pack surfaces."""

from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
from pathlib import Path
from typing import Any


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


def validate_schema(schema_data: dict[str, Any], presets_data: dict[str, Any]) -> None:
    production = set(schema_data["productionAutoProviders"])
    examples = set(schema_data["exampleOnlyProviders"])
    supplemental = set(schema_data["advisoryReviewSupplementalProviders"])
    if production & examples:
        raise ContractError("production and example-only providers overlap")
    if supplemental & production:
        raise ContractError("supplemental providers must be separate from production")

    lanes = set(schema_data["externalOpinionCounts"])
    for profile_name, lanes_map in schema_data["priorityProfiles"].items():
        for lane, providers in lanes_map.items():
            if lane not in lanes:
                raise ContractError(f"profile {profile_name} uses unknown lane {lane}")
            provider_set = set(providers)
            if provider_set & examples:
                raise ContractError(
                    f"profile {profile_name} lane {lane} includes example provider"
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
        validate_defaults(root, schema_data)
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
