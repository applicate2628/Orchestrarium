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

HOOK_EXTS = (".py", ".sh", ".ps1")

# ---------------------------------------------------------------------------
# Canon-derived name lists + declared pack-only exceptions.
# ---------------------------------------------------------------------------

PACK_ONLY_SCRIPTS = {
    "src.claude/agents/scripts": frozenset({
        # Provider-specialized SessionStart context hook: walks the CLAUDE-line
        # .agents-mode.yaml read-order (./.claude/, ~/.claude/) and speaks
        # Agent-tool dispatch idiom; the codex twin walks ./.agents/ + ~/.codex/
        # and speaks role/skill-activation idiom — intentionally different.
        "agents-mode-reminder.sh", "agents-mode-reminder.ps1",
        # Claude-line provider transport wrappers (no codex/canon analog).
        "invoke-claude-api.sh", "invoke-claude-api.ps1",
        "invoke-claude-prompt.sh", "invoke-claude-prompt.ps1",
        "invoke-codex-prompt.sh", "invoke-codex-prompt.ps1",
        # Claude-line active watcher emitted by the Codex dispatch wrappers;
        # it is provider-specific and has no Codex/canon mirror.
        "await-codex-dispatch.sh", "await-codex-dispatch.ps1",
        # Per-pack validator (content differs per pack by design).
        "validate-skill-pack.sh", "validate-skill-pack.ps1",
    }),
    "src.codex/skills/lead/scripts": frozenset({
        "agents-mode-reminder.sh", "agents-mode-reminder.ps1",  # see above
        "validate-skill-pack.sh", "validate-skill-pack.ps1",
    }),
}

PACK_ONLY_HOOKS = {
    "src.claude/agents/hooks": frozenset({
        # Claude-only typed-routing audit: keys on the subagent-dispatch tool
        # (captured tool_name "Agent"). Codex CLI exposes no analogous
        # subagent-dispatch tool, so there is no Codex/canon mirror.
        "check-typed-routing.py", "check-typed-routing.sh", "check-typed-routing.ps1",
    }),
    "src.codex/skills/lead/hooks": frozenset(),
}

MIRROR_SCRIPT_DIRS = ("src.claude/agents/scripts", "src.codex/skills/lead/scripts")
MIRROR_HOOK_DIRS = ("src.claude/agents/hooks", "src.codex/skills/lead/hooks")


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
        names = canon_names(root, subdir)
        c_dir = canon_root(root) / subdir
        for mirror_rel_dir in mirror_dirs:
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
