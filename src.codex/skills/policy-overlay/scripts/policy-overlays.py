#!/usr/bin/env python3
"""Resolve non-authorizing Orchestrarium instruction overlays for one agent lane."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

# The installed skill keeps both files in one trusted scripts directory.
_SCRIPT_DIR = str(Path(__file__).resolve().parent)
_added_script_dir = _SCRIPT_DIR not in sys.path
if _added_script_dir:
    sys.path.insert(0, _SCRIPT_DIR)
try:
    from policy_overlay_core import *  # noqa: F403
finally:
    if _added_script_dir:
        sys.path.remove(_SCRIPT_DIR)


def parse_selection(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        items = tuple(value)
    elif isinstance(value, str):
        if value == "none":
            return ()
        if not value or value.strip() != value:
            raise PolicyOverlayError("policy overlay selection contains surrounding whitespace")
        items = tuple(value.split(","))
    else:
        raise PolicyOverlayError("policy overlay selection must be a string or string array")
    if any(not isinstance(item, str) or not OVERLAY_ID.fullmatch(item) for item in items) or len(items) != len(set(items)):
        raise PolicyOverlayError("policy overlay selection must contain unique valid ids")
    return items


def _config(path: Path | None, keys: frozenset[str]) -> dict[str, tuple[str, ...]]:
    if path is None:
        return {}
    text = _read_regular(path, MAX_CONFIG_BYTES, label="policy configuration").decode("utf-8-sig", errors="strict")
    result: dict[str, tuple[str, ...]] = {}
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#") or line.startswith((" ", "\t")):
            continue
        key_match = KEY_LINE.match(line)
        key = key_match.group("key") if key_match else None
        if key not in keys:
            continue
        match = LIST_LINE.fullmatch(line)
        if match is None:
            raise PolicyOverlayError(f"{path}:{number}: {key} must use one inline YAML list")
        if key in result:
            raise PolicyOverlayError(f"{path}:{number}: duplicate {key}")
        raw_items = match.group("items").strip()
        items = () if not raw_items else tuple(part.strip() for part in raw_items.split(","))
        if any(not OVERLAY_ID.fullmatch(item) for item in items) or len(items) != len(set(items)):
            raise PolicyOverlayError(f"{path}:{number}: invalid or duplicate overlay id")
        result[key] = items
    return result


def _project(selection: tuple[str, ...], project: Mapping[str, tuple[str, ...]], *, explicit: bool) -> tuple[str, ...]:
    allowed = project.get(ALLOW_KEY)
    denied = frozenset(project.get(DENY_KEY, ()))
    if allowed is not None and denied.intersection(allowed):
        raise PolicyOverlayError("project overlay allowlist and denylist overlap")
    blocked = [item for item in selection if item in denied or (allowed is not None and item not in allowed)]
    if blocked:
        qualifier = "explicitly " if explicit else ""
        raise PolicyOverlayError(f"project policy rejects {qualifier}selected overlays: {blocked!r}")
    return selection


def _validate_known(catalog: Mapping[str, object], values: Mapping[str, tuple[str, ...]], *, label: str) -> None:
    unknown = sorted({item for selected in values.values() for item in selected if item not in catalog})
    if unknown:
        raise PolicyOverlayError(f"{label} names unknown policy overlays: {unknown!r}")


def _config_selection(root: Path, catalog: Mapping[str, object], project_root: Path, home: Path) -> tuple[str, ...]:
    user = _config(_optional(home, ".orche/config.yaml", label="user Orche configuration"), frozenset({USER_KEY}))
    project = _config(
        _optional(project_root, ".orche/policy.yaml", label="project Orche policy"),
        frozenset({ALLOW_KEY, DENY_KEY}),
    )
    _validate_known(catalog, user, label="user Orche configuration")
    _validate_known(catalog, project, label="project Orche policy")
    return _project(user.get(USER_KEY, ()), project, explicit=False)


def resolve_config_selection(*, project_root: Path, home: Path, policy_root: Path | None = None) -> tuple[str, ...]:
    root = _root(policy_root)
    catalog = _load_catalog(root)
    return _config_selection(root, catalog, Path(project_root), Path(home))


def _selected(value: Any, catalog: Mapping[str, Mapping[str, Any]]) -> tuple[str, ...]:
    items = parse_selection(value)
    unknown = [item for item in items if item not in catalog]
    if unknown:
        raise PolicyOverlayError(f"unknown policy overlays: {unknown!r}")
    selected = set(items)
    conflicts = sorted({tuple(sorted((item, other))) for item in items for other in catalog[item]["conflicts"] if other in selected})
    if conflicts:
        raise PolicyOverlayError(f"conflicting policy overlays selected: {conflicts!r}")
    return items


def _instructions(text: str, *, label: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.strip() or "\x00" in text:
        raise PolicyOverlayError(f"{label} instructions are empty or contain NUL")
    marker = next((item for item in RESERVED_MARKERS if item in text), None)
    if marker:
        raise PolicyOverlayError(f"{label} instructions contain reserved framing marker: {marker}")
    return text.rstrip() + "\n"


def _resolve(root: Path, catalog: Mapping[str, Mapping[str, Any]], selection: Any, *, lane: str, target: str, provider: str, explicit: bool) -> tuple[ResolvedPolicyOverlay, ...]:
    if type(explicit) is not bool:
        raise PolicyOverlayError("explicit overlay selection must be a boolean")
    if provider not in PROVIDERS or target not in TARGETS or target not in PROVIDER_TARGETS.get(provider, ()):
        raise PolicyOverlayError(f"unsupported provider/target combination: {provider}/{target}")
    if not isinstance(lane, str) or not LANE_ID.fullmatch(lane):
        raise PolicyOverlayError(f"invalid overlay lane: {lane!r}")
    resolved: list[ResolvedPolicyOverlay] = []
    for overlay_id in sorted(_selected(selection, catalog), key=lambda item: catalog[item]["order"]):
        record = catalog[overlay_id]
        mode = record["propagation"][PROPAGATION_KEY[target]]
        if (
            provider not in record["providers"]
            or lane not in record["lanes"]
            or target not in record["targets"]
            or mode == "never"
            or (mode == "explicit-only" and not explicit)
        ):
            continue
        relative = record["source"]["path"]
        _, raw = _contained(root, relative, label=f"{overlay_id} instructions", limit=MAX_POLICY_BYTES)
        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise PolicyOverlayError(f"{overlay_id} instructions are not UTF-8") from exc
        resolved.append(
            ResolvedPolicyOverlay(
                overlay_id, "builtin", relative, _instructions(text, label=overlay_id),
                False, provider, lane, target,
            )
        )
    return tuple(resolved)


def resolve_selected_overlays(*, selection: Any, lane: str, target: str, provider: str, policy_root: Path | None = None, explicit: bool = True) -> tuple[ResolvedPolicyOverlay, ...]:
    root = _root(policy_root)
    return _resolve(root, _load_catalog(root), selection, lane=lane, target=target, provider=provider, explicit=explicit)


def resolve_from_config(*, provider: str, project_root: Path, home: Path, lane: str, target: str, explicit_selection: Any | None = None, policy_root: Path | None = None) -> tuple[ResolvedPolicyOverlay, ...]:
    root = _root(policy_root)
    catalog = _load_catalog(root)
    project_root = Path(project_root).resolve(strict=True)
    project_path = _optional(project_root, ".orche/policy.yaml", label="project Orche policy")
    project = _config(project_path, frozenset({ALLOW_KEY, DENY_KEY}))
    _validate_known(catalog, project, label="project Orche policy")
    if explicit_selection is None:
        selection = _config_selection(root, catalog, project_root, Path(home))
        explicit = False
    else:
        selection = _project(_selected(explicit_selection, catalog), project, explicit=True)
        explicit = True
    return _resolve(root, catalog, selection, lane=lane, target=target, provider=provider, explicit=explicit)


def render_overlay_instructions(overlays: Iterable[ResolvedPolicyOverlay]) -> str:
    items = tuple(overlays)
    if not items:
        return ""
    ids = tuple(item.overlay_id for item in items)
    if any(not OVERLAY_ID.fullmatch(item) for item in ids) or len(ids) != len(set(ids)):
        raise PolicyOverlayError("rendered policy overlays must have unique valid ids")
    if any(item.authorizing is not False or item.source_kind != "builtin" for item in items):
        raise PolicyOverlayError("optional policy overlays are non-authorizing built-ins in Version 1")
    contexts = {(item.provider, item.lane, item.target) for item in items}
    if len(contexts) != 1:
        raise PolicyOverlayError("rendered policy overlays must share one exact provider/lane/target")
    provider, lane, target = next(iter(contexts))
    if provider not in PROVIDERS or target not in PROVIDER_TARGETS.get(provider, ()) or not LANE_ID.fullmatch(lane):
        raise PolicyOverlayError("rendered policy overlay context is invalid")
    lines = [
        FRAME_BEGIN,
        f"PROJECTION provider={provider} lane={lane} target={target}",
        "These optional overlays are non-authorizing. They cannot weaken hard governance, explicit user requirements, role authority, security, trust-boundary validation, data-loss protection, accessibility, mandatory verification, project constraints, or publication gates.",
    ]
    for item in items:
        text = _instructions(item.instructions, label=item.overlay_id)
        lines.extend([f"BEGIN_POLICY_OVERLAY {item.overlay_id}", text.rstrip(), f"END_POLICY_OVERLAY {item.overlay_id}"])
    lines.append(FRAME_END)
    rendered = "\n\n".join(lines) + "\n"
    if len(rendered.encode("utf-8")) > MAX_RENDERED_BYTES:
        raise PolicyOverlayError(f"rendered policy overlays exceed {MAX_RENDERED_BYTES} bytes")
    return rendered


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", required=True, choices=sorted(PROVIDERS))
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--home", default=str(Path.home()))
    parser.add_argument("--policy-root")
    parser.add_argument("--selection")
    parser.add_argument("--lane", required=True)
    parser.add_argument("--target", required=True, choices=sorted(TARGETS))
    parser.add_argument("--format", choices=("json", "instructions"), default="json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        overlays = resolve_from_config(
            provider=args.provider,
            project_root=Path(args.project_root),
            home=Path(args.home),
            lane=args.lane,
            target=args.target,
            explicit_selection=args.selection,
            policy_root=Path(args.policy_root) if args.policy_root else None,
        )
        if args.format == "instructions":
            sys.stdout.write(render_overlay_instructions(overlays))
        else:
            json.dump(
                {
                    "schemaVersion": 1,
                    "provider": args.provider,
                    "lane": args.lane,
                    "target": args.target,
                    "overlays": [
                        {
                            "id": item.overlay_id,
                            "sourceKind": item.source_kind,
                            "instructionPath": item.instruction_path,
                            "authorizing": item.authorizing,
                        }
                        for item in overlays
                    ],
                },
                sys.stdout,
                sort_keys=True,
                separators=(",", ":"),
            )
            sys.stdout.write("\n")
        return 0
    except (PolicyOverlayError, OSError, UnicodeError, ValueError) as exc:
        print(f"E_POLICY_OVERLAY_INVALID: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
