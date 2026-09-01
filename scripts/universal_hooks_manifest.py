"""Single-owner manifest + drift detection for the scripts/universal-hooks/
canon: which mirrored names are canon-tracked, which pack-owned files are
declared exceptions with no canon counterpart, and how to detect drift.

Deliberately dependency-free: no dataclasses, no subprocess, no argparse, no
shutil. This module exists specifically so that importing it — which
tests/test_universal_hook_surfaces.py does, to avoid re-declaring this same
data and risking the two-owners-drift class this repository has spent a lot
of effort repairing elsewhere — can never be broken by a defect in the CLI or
mutation logic of scripts/sync-universal-hooks.py (which imports THIS module,
not the reverse). A bug in that tool's git integration, argparse setup, or
reporting logic must never be able to take down the parity gate's ability to
even COLLECT; only a bug in this small, stable data contract can, and that
surface is intentionally kept tiny and auditable.

(History: an earlier version of this manifest lived inside
scripts/sync-universal-hooks.py itself, keyed to a `@dataclass(frozen=True)`
DriftEntry. Under this machine's Python 3.14, `dataclasses` resolves
stringified annotations via `sys.modules[cls.__module__]`, which is `None`
until the loading module is registered in `sys.modules` BEFORE `exec_module`
runs — an easy thing to get wrong when loading a hyphenated scripts/ file via
importlib, and exactly what happened here. Splitting the manifest out here
does two independent things: it uses `NamedTuple` instead of `dataclass`
(verified empirically to need no such registration), AND it removes the
larger tool's argparse/subprocess/git-integration code from the parity test's
import path entirely, so a *different* future bug in that larger, more
volatile file can no longer take the parity gate down with it either.)
"""

from __future__ import annotations

import filecmp
from pathlib import Path
from typing import NamedTuple

# Registered hooks and the canonical/mirrored hook implementation are Python.
# Public POSIX launchers are catalogued by the production-entrypoint contract;
# they are deliberately not part of this mirror set.
HOOK_EXTS = (".py",)

# Python-owned production entrypoints that intentionally retain a thin POSIX
# launcher but are not registered runtime hooks.  Hook health and wrapper
# reclaim must classify these identically: they remain installed files and
# never become registration prerequisites.
NON_REGISTERED_ENTRYPOINT_STEMS = frozenset({
    "await-codex-dispatch",
    "check-publication-safety",
    "invoke-claude-api",
    "invoke-claude-prompt",
    "invoke-codex-prompt",
    "validate-skill-pack",
})

# ---------------------------------------------------------------------------
# Canon-derived name lists + declared pack-only exceptions.
# ---------------------------------------------------------------------------

PACK_ONLY_SCRIPTS = {
    "src.claude/agents/scripts": frozenset({
        # Provider-specialized SessionStart context hook: walks the CLAUDE-line
        # .agents-mode.yaml read-order (./.claude/, ~/.claude/) and speaks
        # Agent-tool dispatch idiom; the codex twin walks ./.agents/ + ~/.codex/
        # and speaks role/skill-activation idiom — intentionally different.
        "agents-mode-reminder.py",
        # Neutral Claude scalar-precedence support consumed by the delegation
        # reminder and MCP-force adapter; it is support, not a hook entrypoint.
        "agents_mode_runtime.py",
        # Claude's root force-mode binding uses the universal classifier but is
        # provider-specific because Codex intentionally retains warn-only MCP
        # momentum.  The historical Claude hooks/ mirror is excluded below.
        "check-mcp-momentum.py",
        # Claude-line provider transport wrappers (no codex/canon analog).
        "invoke-claude-api.py",
        "invoke-claude-prompt.py",
        "invoke-codex-prompt.py",
        # Claude-line active watcher emitted by the Codex dispatch wrappers;
        # it is provider-specific and has no Codex/canon mirror.
        "await-codex-dispatch.py",
        # Per-pack validator (content differs per pack by design).
        "validate-skill-pack.py",
    }),
    "src.codex/skills/lead/scripts": frozenset({
        "agents-mode-reminder.py",  # see above
        "validate-skill-pack.py",
    }),
}

PACK_ONLY_HOOKS = {
    "src.claude/agents/hooks": frozenset({
        # Claude-only typed-routing audit: keys on the subagent-dispatch tool
        # (captured tool_name "Agent"). Codex CLI exposes no analogous
        # subagent-dispatch tool, so there is no Codex/canon mirror.
        "check-typed-routing.py",
        # Dispatch-time invariant registry (round-depth observer,
        # work-items/active/2026-07-26-registry-bug-sweep/
        # design-round-cap-observer.md), imported by check-typed-routing.py
        # above -- not a registered hook entry itself (no shell wrapper),
        # so it carries no hooks.json/installer obligation. Single-tree for
        # the same reason as its adapter: it keys on the Agent dispatch tool,
        # which Codex CLI has no analog for.
        "dispatch_sentinels.py",
    }),
    "src.codex/skills/lead/hooks": frozenset(),
}

# Single source of truth for the Python targets that are registered as hooks.
# Canon files such as hook_common.py and check-publication-safety.py are support
# or manual-command surfaces, not hook registrations. Provider-only files are
# similarly registered only when this mapping names them.
REGISTERED_HOOK_STEMS_BY_PLATFORM = {
    "claude": frozenset({
        "agents-mode-reminder",
        "check-bugfix-discipline",
        "check-git-push-gate",
        "check-machine-local-path",
        "check-mcp-momentum",
        "check-no-trash-in-repo",
        "check-passive-polling-stop",
        "check-repository-orientation",
        "check-scratch-valuables",
        "check-stale-relation-residue",
        "check-typed-routing",
        "mcp-usage-reminder",
        "turn-anchor-reminder",
    }),
    "codex": frozenset({
        "agents-mode-reminder",
        "check-bugfix-discipline",
        "check-git-push-gate",
        "check-machine-local-path",
        "check-mcp-momentum",
        "check-no-trash-in-repo",
        "check-passive-polling-stop",
        "check-repository-orientation",
        "check-scratch-valuables",
        "check-stale-relation-residue",
        "mcp-usage-reminder",
        "turn-anchor-reminder",
    }),
}

MIRROR_SCRIPT_DIRS = ("src.claude/agents/scripts", "src.codex/skills/lead/scripts")
MIRROR_HOOK_DIRS = ("src.claude/agents/hooks", "src.codex/skills/lead/hooks")

# A universal implementation may be specialized by one provider at a different
# source-hygiene placement.  Exclusions are explicit and path-scoped so a
# provider cannot silently drop an otherwise universal file.
MIRROR_EXCLUSIONS = {
    "src.claude/agents/hooks": frozenset({"check-mcp-momentum.py"}),
}


def canon_root(root: Path) -> Path:
    return root / "scripts" / "universal-hooks"


def canon_names(root: Path, subdir: str) -> tuple[str, ...]:
    """Derive the required-name list by GLOB of the canon dir itself — never a
    hardcoded tuple, so a new universal hook/script is picked up automatically
    and a stale name disappears automatically."""
    d = canon_root(root) / subdir
    return tuple(sorted(
        p.name for p in d.iterdir()
        if p.is_file() and p.suffix in HOOK_EXTS
    ))


def registered_hook_stems(platform: str) -> frozenset[str]:
    """Return the complete hook-registration set for one production provider."""
    try:
        return REGISTERED_HOOK_STEMS_BY_PLATFORM[platform]
    except KeyError as exc:
        raise ValueError(f"unsupported platform: {platform}") from exc


def mirror_names(root: Path, subdir: str, mirror_rel_dir: str) -> tuple[str, ...]:
    """Return the canon-derived names owned by one concrete mirror."""
    excluded = MIRROR_EXCLUSIONS.get(mirror_rel_dir, frozenset())
    return tuple(name for name in canon_names(root, subdir) if name not in excluded)


# ---------------------------------------------------------------------------
# Drift detection (shared by the --check CLI surface and the parity test).
# ---------------------------------------------------------------------------

class DriftEntry(NamedTuple):
    canon_path: Path
    mirror_path: Path
    mirror_rel: str  # e.g. "src.claude/agents/scripts/check-foo.py", posix-style


def find_drift(root: Path) -> list[DriftEntry]:
    drift: list[DriftEntry] = []
    for subdir, mirror_dirs in (("scripts", MIRROR_SCRIPT_DIRS), ("hooks", MIRROR_HOOK_DIRS)):
        c_dir = canon_root(root) / subdir
        for mirror_rel_dir in mirror_dirs:
            names = mirror_names(root, subdir, mirror_rel_dir)
            m_dir = root / Path(mirror_rel_dir)
            for name in names:
                c_path = c_dir / name
                m_path = m_dir / name
                if not m_path.is_file() or not filecmp.cmp(c_path, m_path, shallow=False):
                    drift.append(DriftEntry(
                        canon_path=c_path,
                        mirror_path=m_path,
                        mirror_rel=f"{mirror_rel_dir}/{name}",
                    ))
    return drift
