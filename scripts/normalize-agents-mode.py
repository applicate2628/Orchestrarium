#!/usr/bin/env python3
"""Normalize an Orchestrarium agents-mode file to the current canonical form.

This helper preserves effective scalar settings, refreshes shipped canonical
blocks from the current template, keeps custom profiles/count lanes, drops
retired canonical keys, and restores the current inline comments/order.
"""

from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass, field


TOP_KEY_RE = re.compile(r"^([A-Za-z][A-Za-z0-9]*):(?:\s*(.*))?$")
INDENT2_KEY_RE = re.compile(r"^ {2}([^:#][^:]*):(?:\s*(.*))?$")
INDENT4_KEY_RE = re.compile(r"^ {4}([^:#][^:]*):\s*(.*)$")
RETIRED_PROFILE_NAMES = {"gemini-crosscheck"}
PRODUCTION_PROFILE_PROVIDERS = {"codex", "claude"}
ADVISORY_REVIEW_PROFILE_PROVIDERS = {"codex", "claude", "claude-secret"}


@dataclass
class ScalarMeta:
    value: str
    comment: str


@dataclass
class LaneMeta:
    value: str
    comment: str


@dataclass
class ProfileMeta:
    comment: str
    lane_order: list[str] = field(default_factory=list)
    lanes: dict[str, LaneMeta] = field(default_factory=dict)


@dataclass
class BlockMeta:
    comment: str
    order: list[str] = field(default_factory=list)
    entries: dict[str, ProfileMeta | LaneMeta] = field(default_factory=dict)


def split_value_and_comment(rest: str | None) -> tuple[str, str]:
    raw = "" if rest is None else rest.rstrip()
    if raw.startswith("#"):
        return "", raw.strip()
    match = re.search(r"\s+#", raw)
    if not match:
        return raw.strip(), ""
    value = raw[: match.start()].rstrip()
    comment = raw[match.start() :].strip()
    return value, comment


def collect_top_level_blocks(lines: list[str]) -> tuple[list[str], dict[str, list[str]]]:
    order: list[str] = []
    blocks: dict[str, list[str]] = {}
    current_key: str | None = None

    for line in lines:
        match = TOP_KEY_RE.match(line)
        if match and not line.startswith(" "):
            current_key = match.group(1)
            order.append(current_key)
            blocks[current_key] = [line]
            continue
        if current_key is not None:
            blocks[current_key].append(line)

    return order, blocks


def parse_scalar_block(lines: list[str]) -> ScalarMeta:
    match = TOP_KEY_RE.match(lines[0])
    if not match:
        raise ValueError(f"Invalid scalar line: {lines[0]!r}")
    value, comment = split_value_and_comment(match.group(2))
    return ScalarMeta(value=value, comment=comment)


def parse_priority_profiles_block(lines: list[str]) -> BlockMeta:
    header_match = TOP_KEY_RE.match(lines[0])
    if not header_match:
        raise ValueError(f"Invalid block line: {lines[0]!r}")
    _, header_comment = split_value_and_comment(header_match.group(2))
    result = BlockMeta(comment=header_comment)
    current_profile: str | None = None

    for line in lines[1:]:
        profile_match = INDENT2_KEY_RE.match(line)
        lane_match = INDENT4_KEY_RE.match(line)

        if profile_match and not line.startswith("    "):
            profile_name = profile_match.group(1).strip()
            _, profile_comment = split_value_and_comment(profile_match.group(2))
            result.order.append(profile_name)
            result.entries[profile_name] = ProfileMeta(comment=profile_comment)
            current_profile = profile_name
            continue

        if lane_match and current_profile is not None:
            lane_name = lane_match.group(1).strip()
            value, lane_comment = split_value_and_comment(lane_match.group(2))
            providers = value.strip()
            if providers.startswith("[") and providers.endswith("]"):
                providers = providers[1:-1].strip()
            providers = ", ".join(
                part.strip() for part in providers.split(",") if part.strip()
            )
            profile = result.entries[current_profile]
            assert isinstance(profile, ProfileMeta)
            profile.lane_order.append(lane_name)
            profile.lanes[lane_name] = LaneMeta(value=providers, comment=lane_comment)

    return result


def parse_counts_block(lines: list[str]) -> BlockMeta:
    header_match = TOP_KEY_RE.match(lines[0])
    if not header_match:
        raise ValueError(f"Invalid block line: {lines[0]!r}")
    _, header_comment = split_value_and_comment(header_match.group(2))
    result = BlockMeta(comment=header_comment)

    for line in lines[1:]:
        item_match = INDENT2_KEY_RE.match(line)
        if not item_match:
            continue
        lane_name = item_match.group(1).strip()
        value, lane_comment = split_value_and_comment(item_match.group(2))
        result.order.append(lane_name)
        result.entries[lane_name] = LaneMeta(value=value, comment=lane_comment)

    return result


def comment_suffix(comment: str) -> str:
    return f"  {comment}" if comment else ""


def is_advisory_or_review_lane(lane_name: str) -> bool:
    return lane_name.startswith("advisory.") or lane_name.startswith("review.")


def sanitize_profile_providers(value: str, lane_name: str) -> str:
    """Keep profile providers on production-approved providers for the lane."""
    allowed = (
        ADVISORY_REVIEW_PROFILE_PROVIDERS
        if is_advisory_or_review_lane(lane_name)
        else PRODUCTION_PROFILE_PROVIDERS
    )
    providers: list[str] = []
    for raw_part in value.split(","):
        provider = raw_part.strip().lower()
        if provider in allowed and provider not in providers:
            providers.append(provider)
    return ", ".join(providers)


def read_text_lines(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read().splitlines()


def template_metadata(template_path: str, provider: str) -> tuple[list[str], dict[str, ScalarMeta], BlockMeta, BlockMeta]:
    order, blocks = collect_top_level_blocks(read_text_lines(template_path))
    scalar_meta: dict[str, ScalarMeta] = {}
    profiles_meta: BlockMeta | None = None
    counts_meta: BlockMeta | None = None

    for key in order:
        if key == "externalPriorityProfiles":
            profiles_meta = parse_priority_profiles_block(blocks[key])
        elif key == "externalOpinionCounts":
            counts_meta = parse_counts_block(blocks[key])
        else:
            scalar_meta[key] = parse_scalar_block(blocks[key])

    if profiles_meta is None or counts_meta is None:
        raise ValueError("Template is missing required priority/count blocks.")

    if provider == "codex" and "externalClaudeProfile" not in scalar_meta:
        order.append("externalClaudeProfile")
        scalar_meta["externalClaudeProfile"] = ScalarMeta(
            value="opus-max",
            comment="# allowed: sonnet-high | opus-max; default: opus-max",
        )

    return order, scalar_meta, profiles_meta, counts_meta


def existing_metadata(
    target_path: str | None,
    known_keys: set[str],
    retired_keys: set[str],
) -> tuple[dict[str, ScalarMeta], BlockMeta | None, BlockMeta | None, list[tuple[str, list[str]]]]:
    scalar_values: dict[str, ScalarMeta] = {}
    profiles_block: BlockMeta | None = None
    counts_block: BlockMeta | None = None
    unknown_blocks: list[tuple[str, list[str]]] = []

    if not target_path or not os.path.exists(target_path):
        return scalar_values, profiles_block, counts_block, unknown_blocks

    order, blocks = collect_top_level_blocks(read_text_lines(target_path))
    for key in order:
        if key in retired_keys:
            continue
        if key == "externalPriorityProfiles":
            profiles_block = parse_priority_profiles_block(blocks[key])
            continue
        if key == "externalOpinionCounts":
            counts_block = parse_counts_block(blocks[key])
            continue
        if key in known_keys:
            scalar_values[key] = parse_scalar_block(blocks[key])
            continue
        unknown_blocks.append((key, blocks[key]))

    return scalar_values, profiles_block, counts_block, unknown_blocks


def render_scalar(key: str, meta: ScalarMeta, existing: dict[str, ScalarMeta]) -> list[str]:
    current = existing.get(key)
    value = current.value if current and current.value else meta.value
    if key == "externalPriorityProfile" and value in RETIRED_PROFILE_NAMES:
        value = meta.value
    return [f"{key}: {value}{comment_suffix(meta.comment)}"]


def render_profiles(
    meta: BlockMeta,
    existing: BlockMeta | None,
) -> list[str]:
    lines = [f"externalPriorityProfiles:{comment_suffix(meta.comment)}"]
    existing_profiles = existing.entries if existing else {}
    existing_order = existing.order if existing else []

    for profile_name in meta.order:
        profile_meta = meta.entries[profile_name]
        assert isinstance(profile_meta, ProfileMeta)
        lines.append(f"  {profile_name}:{comment_suffix(profile_meta.comment)}")

        existing_profile = existing_profiles.get(profile_name)
        existing_lane_order: list[str] = []
        existing_lanes: dict[str, LaneMeta] = {}
        if isinstance(existing_profile, ProfileMeta):
            existing_lane_order = existing_profile.lane_order
            existing_lanes = existing_profile.lanes

        for lane_name in profile_meta.lane_order:
            lane_meta = profile_meta.lanes[lane_name]
            lines.append(
                f"    {lane_name}: [{lane_meta.value}]{comment_suffix(lane_meta.comment)}"
            )

        for lane_name in existing_lane_order:
            if lane_name in profile_meta.lanes:
                continue
            extra_lane = existing_lanes[lane_name]
            sanitized_value = sanitize_profile_providers(extra_lane.value, lane_name)
            if not sanitized_value:
                continue
            lines.append(
                f"    {lane_name}: [{sanitized_value}]{comment_suffix(extra_lane.comment)}"
            )

    for profile_name in existing_order:
        if profile_name in meta.entries:
            continue
        if profile_name in RETIRED_PROFILE_NAMES:
            continue
        existing_profile = existing_profiles.get(profile_name)
        if not isinstance(existing_profile, ProfileMeta):
            continue
        lines.append(f"  {profile_name}:{comment_suffix(existing_profile.comment)}")
        for lane_name in existing_profile.lane_order:
            lane = existing_profile.lanes[lane_name]
            sanitized_value = sanitize_profile_providers(lane.value, lane_name)
            if not sanitized_value:
                continue
            lines.append(
                f"    {lane_name}: [{sanitized_value}]{comment_suffix(lane.comment)}"
            )

    return lines


def render_counts(meta: BlockMeta, existing: BlockMeta | None) -> list[str]:
    lines = [f"externalOpinionCounts:{comment_suffix(meta.comment)}"]
    existing_entries = existing.entries if existing else {}
    existing_order = existing.order if existing else []

    for lane_name in meta.order:
        lane_meta = meta.entries[lane_name]
        assert isinstance(lane_meta, LaneMeta)
        existing_lane = existing_entries.get(lane_name)
        value = lane_meta.value
        if isinstance(existing_lane, LaneMeta) and existing_lane.value:
            value = existing_lane.value
        lines.append(f"  {lane_name}: {value}{comment_suffix(lane_meta.comment)}")

    for lane_name in existing_order:
        if lane_name in meta.entries:
            continue
        existing_lane = existing_entries.get(lane_name)
        if not isinstance(existing_lane, LaneMeta):
            continue
        lines.append(
            f"  {lane_name}: {existing_lane.value}{comment_suffix(existing_lane.comment)}"
        )

    return lines


def normalize_file(template: str, target: str, provider: str) -> str:
    order, scalar_meta, profiles_meta, counts_meta = template_metadata(template, provider)
    known_keys = set(order) | {"externalPriorityProfiles", "externalOpinionCounts"}
    retired_keys = {
        "externalClaudeSecretMode",
        "externalGeminiFallbackMode",
        "externalGeminiWorkdirMode",
    }
    if provider != "codex":
        retired_keys.add("externalClaudeProfile")

    existing_scalars, existing_profiles, existing_counts, unknown_blocks = existing_metadata(
        target if os.path.exists(target) else None,
        known_keys=known_keys,
        retired_keys=retired_keys,
    )

    output: list[str] = []
    for key in order:
        if key == "externalPriorityProfiles":
            output.extend(render_profiles(profiles_meta, existing_profiles))
        elif key == "externalOpinionCounts":
            output.extend(render_counts(counts_meta, existing_counts))
        else:
            output.extend(render_scalar(key, scalar_meta[key], existing_scalars))

    for _, raw_block in unknown_blocks:
        if raw_block:
            output.extend(raw_block)

    return "\n".join(output) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--provider", choices=("shared", "codex"), default="shared")
    args = parser.parse_args()

    content = normalize_file(args.template, args.target, args.provider)
    os.makedirs(os.path.dirname(os.path.abspath(args.target)), exist_ok=True)
    with open(args.target, "w", encoding="utf-8", newline="") as handle:
        handle.write(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
