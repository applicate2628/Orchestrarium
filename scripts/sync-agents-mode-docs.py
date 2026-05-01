#!/usr/bin/env python3
"""Synchronize agents-mode reference/init snippets from the JSON contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REFERENCE_DOC = Path("docs/agents-mode-reference.md")
INIT_SURFACES = {
    "codex": Path("src.codex/skills/init-project/SKILL.md"),
    "claude": Path("src.claude/commands/agents-init-project.md"),
    "gemini": Path("src.gemini/skills/init-project/SKILL.md"),
    "qwen": Path("src.qwen/skills/init-project/SKILL.md"),
}

INIT_ROLE_LABELS = {
    "default": "safe-init",
    "absolute-balance": "everyday center",
    "external-aggressive": "aggressive external use",
    "correctness-first": "no-time-limit correctness",
    "power-mode": "hardest-task maximum result",
    "max-speed": "speed-first",
}


class SyncError(Exception):
    """Raised when a generated documentation surface cannot be synchronized."""


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SyncError(f"{path} must contain a JSON object")
    return data


def code(value: str) -> str:
    return f"`{value}`"


def render_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def preset_order(presets_data: dict[str, Any]) -> list[str]:
    return [str(preset) for preset in presets_data["presetOrder"]]


def preset_map(presets_data: dict[str, Any]) -> dict[str, Any]:
    return presets_data["presets"]


def reference_count_cell(mode: str) -> str:
    if mode == "all-1":
        return "all `1`"
    if mode == "advisory-review-2":
        return "advisory+review `2`, others `1`"
    raise SyncError(f"unknown externalOpinionCounts mode: {mode}")


def init_count_cell(mode: str) -> str:
    if mode == "all-1":
        return "all `1`"
    if mode == "advisory-review-2":
        return "advisory+review lanes `2`, others `1`"
    raise SyncError(f"unknown externalOpinionCounts mode: {mode}")


def preset_value_cell(value: str) -> str:
    if value == "shipped-as-is":
        return "shipped as-is"
    return code(value)


def reference_available_presets_table(presets_data: dict[str, Any]) -> str:
    presets = preset_map(presets_data)
    rows = [
        [code(name), presets[name]["role"], presets[name]["whenToUse"]]
        for name in preset_order(presets_data)
    ]
    return render_table(["Preset", "Role", "When to use"], rows)


def reference_expansion_table(presets_data: dict[str, Any]) -> str:
    order = preset_order(presets_data)
    presets = preset_map(presets_data)
    headers = ["Key"] + [code(preset) for preset in order]
    rows: list[list[str]] = []

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
        rows.append(
            [code(key)]
            + [code(str(presets[preset]["expansion"][key])) for preset in order]
        )

    rows.append(
        [code("externalOpinionCounts")]
        + [
            reference_count_cell(str(presets[preset]["expansion"]["externalOpinionCounts"]))
            for preset in order
        ]
    )
    rows.append(
        ["workdir modes"]
        + [
            f"all `{presets[preset]['expansion']['externalCodexWorkdirMode']}`"
            for preset in order
        ]
    )
    rows.append(
        [code("externalModelMode")]
        + [
            code(str(presets[preset]["expansion"]["externalModelMode"]))
            for preset in order
        ]
    )
    rows.append(
        ["`externalClaudeProfile` (Codex-line only)"]
        + [
            code(str(presets[preset]["expansion"]["externalClaudeProfile"]))
            for preset in order
        ]
    )
    return render_table(headers, rows)


def init_expansion_table(presets_data: dict[str, Any], provider: str) -> str:
    order = preset_order(presets_data)
    presets = preset_map(presets_data)
    headers = ["Key"] + [
        f"`{preset}` ({INIT_ROLE_LABELS[preset]})" for preset in order
    ]
    keys = [
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
    ]
    if provider == "codex":
        keys.append("externalClaudeProfile")

    rows: list[list[str]] = []
    for key in keys:
        row = [code(key)]
        for preset in order:
            value = str(presets[preset]["expansion"][key])
            if key == "externalOpinionCounts":
                row.append(init_count_cell(value))
            else:
                row.append(preset_value_cell(value))
        rows.append(row)
    return render_table(headers, rows)


def raised_count_block(presets_data: dict[str, Any]) -> str:
    lines = ["`correctness-first` and `power-mode` lane-specific opinion counts:"]
    lines.extend(
        f"- `{lane}: 2`" for lane in presets_data["raisedOpinionCountLanes"]
    )
    lines.append("- all other lanes: `1`")
    return "\n".join(lines)


def scalar_keys_for_provider(
    schema_data: dict[str, Any],
    provider: str,
) -> list[dict[str, Any]]:
    result = []
    for scalar in schema_data["scalarKeys"]:
        providers = scalar.get("providers")
        if providers and provider not in providers:
            continue
        result.append(scalar)
    return result


def scalar_comment(scalar: dict[str, Any], provider: str) -> str:
    name = scalar["name"]
    allowed = " | ".join(str(value) for value in scalar["allowed"])
    default = scalar["default"]
    if name == "externalProvider":
        if provider == "qwen":
            return (
                f"# allowed here: {allowed}; default: {default}; "
                "gemini/qwen are WEAK MODEL / NOT RECOMMENDED example-only routes"
            )
        return (
            f"# allowed here: {allowed}; default: {default}; "
            "gemini/qwen are explicit example-only and not recommended"
        )
    return f"# allowed: {allowed}; default: {default}"


def canonical_shape(schema_data: dict[str, Any], provider: str) -> str:
    lines: list[str] = []
    for scalar in scalar_keys_for_provider(schema_data, provider):
        name = scalar["name"]
        lines.append(f"{name}: {{value}}  {scalar_comment(scalar, provider)}")
        if name != "reserveResolver":
            continue

        if provider in {"gemini", "qwen"}:
            lines.extend(render_profile_yaml(schema_data["priorityProfiles"]))
            lines.extend(render_counts_yaml(schema_data["externalOpinionCounts"]))
        else:
            lines.append(
                "externalPriorityProfiles: {value}  # allowed: structured profile map"
            )
            lines.append(
                "externalOpinionCounts: {value}  # allowed: structured lane-count map"
            )
    return "\n".join(lines)


def render_profile_yaml(profiles: dict[str, dict[str, list[str]]]) -> list[str]:
    lines = ["externalPriorityProfiles:"]
    for profile_name, lanes in profiles.items():
        lines.append(f"  {profile_name}:")
        for lane_name, providers in lanes.items():
            lines.append(f"    {lane_name}: [{', '.join(providers)}]")
    return lines


def render_counts_yaml(counts: dict[str, int]) -> list[str]:
    lines = ["externalOpinionCounts:"]
    for lane_name, value in counts.items():
        lines.append(f"  {lane_name}: {value}")
    return lines


def replace_table_after_heading(text: str, heading: str, replacement: str) -> str:
    lines = text.splitlines()
    heading_index = find_line(lines, heading)
    start = None
    for index in range(heading_index + 1, len(lines)):
        if lines[index].startswith("|"):
            start = index
            break
    if start is None:
        raise SyncError(f"missing table after heading {heading!r}")
    end = start
    while end < len(lines) and lines[end].startswith("|"):
        end += 1
    new_lines = lines[:start] + replacement.splitlines() + lines[end:]
    return "\n".join(new_lines) + "\n"


def replace_raised_count_block(text: str, replacement: str) -> str:
    lines = text.splitlines()
    start = find_line(
        lines,
        "`correctness-first` and `power-mode` lane-specific opinion counts:",
    )
    end = start + 1
    while end < len(lines) and lines[end].startswith("- "):
        end += 1
    new_lines = lines[:start] + replacement.splitlines() + lines[end:]
    return "\n".join(new_lines) + "\n"


def replace_canonical_shape(text: str, replacement: str) -> str:
    lines = text.splitlines()
    marker = None
    for index, line in enumerate(lines):
        if "Use this canonical" in line:
            marker = index
            break
    if marker is None:
        raise SyncError("missing canonical shape marker")

    start = None
    for index in range(marker + 1, len(lines)):
        if lines[index].strip() == "```yaml":
            start = index
            break
    if start is None:
        raise SyncError("missing canonical shape YAML fence")

    end = None
    for index in range(start + 1, len(lines)):
        if lines[index].strip() == "```":
            end = index
            break
    if end is None:
        raise SyncError("unterminated canonical shape YAML fence")

    indent = lines[start][: len(lines[start]) - len(lines[start].lstrip())]
    replacement_lines = [
        f"{indent}{line}" if line else "" for line in replacement.splitlines()
    ]
    new_lines = lines[: start + 1] + replacement_lines + lines[end:]
    return "\n".join(new_lines) + "\n"


def find_line(lines: list[str], expected: str) -> int:
    for index, line in enumerate(lines):
        if line == expected:
            return index
    raise SyncError(f"missing line {expected!r}")


def generated_reference_text(
    original: str,
    presets_data: dict[str, Any],
) -> str:
    text = replace_table_after_heading(
        original,
        "### Available presets",
        reference_available_presets_table(presets_data),
    )
    text = replace_table_after_heading(
        text,
        "### Preset expansion table",
        reference_expansion_table(presets_data),
    )
    return replace_raised_count_block(text, raised_count_block(presets_data))


def generated_init_text(
    original: str,
    schema_data: dict[str, Any],
    presets_data: dict[str, Any],
    provider: str,
) -> str:
    text = replace_table_after_heading(
        original,
        "## Preset expansion table",
        init_expansion_table(presets_data, provider),
    )
    text = replace_raised_count_block(text, raised_count_block(presets_data))
    return replace_canonical_shape(text, canonical_shape(schema_data, provider))


def target_updates(root: Path) -> dict[Path, str]:
    schema_data = load_json(root / "shared" / "agents-mode.schema.json")
    presets_data = load_json(root / "shared" / "agents-mode.presets.json")

    updates: dict[Path, str] = {}
    reference_path = root / REFERENCE_DOC
    updates[reference_path] = generated_reference_text(
        reference_path.read_text(encoding="utf-8"),
        presets_data,
    )
    for provider, relative_path in INIT_SURFACES.items():
        full_path = root / relative_path
        updates[full_path] = generated_init_text(
            full_path.read_text(encoding="utf-8"),
            schema_data,
            presets_data,
            provider,
        )
    return updates


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="repository root")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="fail if generated docs drift")
    mode.add_argument("--write", action="store_true", help="rewrite generated docs")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    updates = target_updates(root)
    changed: list[Path] = []
    for path, new_text in updates.items():
        old_text = path.read_text(encoding="utf-8")
        if old_text != new_text:
            changed.append(path)
            if args.write:
                path.write_text(new_text, encoding="utf-8", newline="")

    if changed and args.check:
        for path in changed:
            print(f"FAIL: {path.relative_to(root)} is not synced", file=sys.stderr)
        return 1

    if changed:
        for path in changed:
            print(f"UPDATED: {path.relative_to(root)}")
    print("PASS: agents-mode docs are synced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
