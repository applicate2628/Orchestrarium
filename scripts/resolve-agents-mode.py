#!/usr/bin/env python3
"""Resolve effective Orchestrarium agents-mode values across precedence layers."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any


PROVIDER_DIRS = {
    "codex": ".agents",
    "claude": ".claude",
    "gemini": ".gemini",
    "qwen": ".qwen",
}


def _load_normalizer(repo_root: Path):
    normalizer_path = repo_root / "scripts" / "normalize-agents-mode.py"
    spec = importlib.util.spec_from_file_location("_agents_mode_normalizer", normalizer_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {normalizer_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def strip_comment(value: str) -> str:
    return value.split(" #", 1)[0].strip()


def parse_provider_list(value: str) -> list[str]:
    value = strip_comment(value)
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    return [provider.strip() for provider in value.split(",") if provider.strip()]


def parse_agents_mode_text(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    current_block: str | None = None
    current_profile: str | None = None

    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" ") and ":" in line:
            key, rest = line.split(":", 1)
            current_block = key.strip()
            current_profile = None
            if current_block == "externalPriorityProfiles":
                result[current_block] = {}
            elif current_block == "externalOpinionCounts":
                result[current_block] = {}
            else:
                result[current_block] = strip_comment(rest)
            continue

        if current_block == "externalPriorityProfiles":
            if line.startswith("  ") and not line.startswith("    ") and ":" in line:
                current_profile = line.split(":", 1)[0].strip()
                result[current_block][current_profile] = {}
                continue
            if line.startswith("    ") and current_profile and ":" in line:
                lane, rest = line.split(":", 1)
                result[current_block][current_profile][lane.strip()] = parse_provider_list(rest)
                continue

        if current_block == "externalOpinionCounts":
            if line.startswith("  ") and ":" in line:
                lane, rest = line.split(":", 1)
                value = strip_comment(rest)
                try:
                    result[current_block][lane.strip()] = int(value)
                except ValueError:
                    result[current_block][lane.strip()] = value

    return result


def canonical_defaults(repo_root: Path, provider: str) -> dict[str, Any]:
    normalizer = _load_normalizer(repo_root)
    template = repo_root / "shared" / "agents-mode.defaults.yaml"
    missing_target = repo_root / ".scratch" / "__agents_mode_missing__"
    normalizer_provider = "codex" if provider == "codex" else "shared"
    content = normalizer.normalize_file(str(template), str(missing_target), normalizer_provider)
    return parse_agents_mode_text(content)


def layer_paths(provider: str, project_root: Path, home: Path) -> list[tuple[str, Path]]:
    provider_dir = PROVIDER_DIRS[provider]
    return [
        ("local", project_root / provider_dir / ".agents-mode.yaml"),
        ("local-legacy", project_root / provider_dir / ".agents-mode"),
        ("global", home / f".{provider}" / ".agents-mode.yaml"),
        ("global-legacy", home / f".{provider}" / ".agents-mode"),
        ("shared-global", home / ".agents-mode.yaml"),
    ]


def resolve(provider: str, project_root: Path, home: Path, repo_root: Path) -> dict[str, Any]:
    values: dict[str, Any] = {}
    sources: dict[str, dict[str, str]] = {}

    for rank, path in layer_paths(provider, project_root, home):
        if not path.is_file():
            continue
        parsed = parse_agents_mode_text(path.read_text(encoding="utf-8"))
        for key, value in parsed.items():
            if key in values:
                continue
            values[key] = value
            sources[key] = {"rank": rank, "path": str(path)}

    for key, value in canonical_defaults(repo_root, provider).items():
        if key in values:
            continue
        values[key] = value
        sources[key] = {"rank": "defaults", "path": str(repo_root / "shared" / "agents-mode.defaults.yaml")}

    return {
        "provider": provider,
        "projectRoot": str(project_root),
        "home": str(home),
        "values": values,
        "sources": sources,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=sorted(PROVIDER_DIRS), required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--home", default=str(Path.home()))
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--json", action="store_true", help="emit JSON output")
    args = parser.parse_args()

    resolved = resolve(
        args.provider,
        Path(args.project_root).resolve(),
        Path(os.path.expanduser(args.home)).resolve(),
        Path(args.repo_root).resolve(),
    )
    if args.json:
        json.dump(resolved, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0

    for key, value in resolved["values"].items():
        source = resolved["sources"][key]
        print(f"{key}: {value}  # {source['rank']} {source['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
