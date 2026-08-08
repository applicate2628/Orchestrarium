#!/usr/bin/env python3
"""Shared Python owner for the production Codex and Claude pack installers."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


CODEX_BEGIN = "<!-- BEGIN ORCHESTRARIUM CODEX PACK -->"
CODEX_END = "<!-- END ORCHESTRARIUM CODEX PACK -->"
RUNTIME_HELPERS = (
    "agent-run-ledger.py",
    "agent-run-ledger.sh",
    "bash_runtime.py",
    "check-work-items-state.py",
    "check-work-items-state.sh",
    "mutate-work-item.py",
    "skill_pack_validator_runtime.py",
    "validate-work-item-state.py",
    "validate-work-item-state.sh",
)
CODEX_RUNTIME_HELPERS = ("check-hook-health.py",)
CODEX_HOOK_INVENTORY = "codex-hook-inventory.json"
# SHA-256 fingerprints of every historically shipped Codex built-in agent
# override, after the same newline normalization used by reclaim. Current
# source files are compared directly and are deliberately not duplicated here.
# The three entries per file are, in order-independent form: gpt-5.5 with the
# current overlay text, gpt-5.4 with that text, and gpt-5.4 with the earlier
# instructions. Arbitrary model values are not pack ownership evidence.
HISTORICAL_CODEX_AGENT_SHA256 = {
    "default.toml": frozenset(
        {
            "424ac911c141fa39a3d9f17dcf7c141f6fb5168dffda1d6d68ca91f11f67eb55",
            "56c4b7682189f2d17e8f07276410e6eeb551a184d5c32fdf0bd693642e643c21",
            "e6a926a23717cee6b76de5994d10ad5786f2d118018e44ccaf6d88685c124ce0",
        }
    ),
    "explorer.toml": frozenset(
        {
            "c749b9efb338ab067355f6b659439ab456f766fc36296a8dba94b13a471dbb1e",
            "ff67c74ff03bc1c61af67ba22d934275a02f8b0d253e74e402d8c46c3760d510",
            "c8081cc31a07a27b4c288ccb723cb8b08e8939bf25e516acf939ef7462342008",
        }
    ),
    "worker.toml": frozenset(
        {
            "ece7e2c101144c94c6fa3edc8304ecf9a0d384ca44fd0ca747a9c57960db045c",
            "a843c3b41f8bad74cf2ee2232fdcc061adc6ad34eb1c55ea55913d70d4be3cc6",
            "eab205b036bb4e7b7765f0749c7a0739ce7f16eafb782a23bbc0d2494c95fdb2",
        }
    ),
}

# SHA-256 fingerprints of the last production PowerShell files. Upgrade cleanup
# removes only an exact byte-for-byte pack copy; any edited file is preserved.
_CODEX_RETIRED_PS1 = {
    "skills/lead/scripts/validate-skill-pack.ps1": "7ddbd4ef206c66fdee7742f56463fbc2f4db6049f2630b3ec57a7f94cc65e02e",
    "skills/lead/scripts/turn-anchor-reminder.ps1": "edf6aef1861337d3cda0dc142c64bb28ed797c48670a379c4ca0a51a0f8d58d0",
    "skills/lead/scripts/mcp-usage-reminder.ps1": "62c9990f57ee7eccadcf1504a638ff6cbe4b61548405288d70ed192254b54d3d",
    "skills/lead/scripts/check-work-items-archival-stop.ps1": "16d7cc086c34ddd8b571ad1b0e926afd74114e88d0b80a4c422c2ec2875e82ae",
    "skills/lead/scripts/check-work-items-archival-stop.py": "6fd48cbfb64e0861a5f8ad6c2c011fa6ae9dfd8567b1636dc2cf6b1ab18e11a1",
    "skills/lead/scripts/check-work-items-archival-stop.sh": "3c5dbc2499b6694859c71b2478e49f92b9fe45369d5287ea16463bacf6f84628",
    "skills/lead/scripts/check-scratch-valuables.ps1": "1aa910d0557bfc1abedd65d7c3e30c53bab4fc7147dbc453199ec60f37ec0b22",
    "skills/lead/scripts/check-publication-safety.ps1": "0e0b8b9a41140a58a82e59d4a21bca59b9922952872613819995c31036a3b3df",
    "skills/lead/scripts/check-passive-polling-stop.ps1": "04790e77b1c08d0d38767030531008739b9550664f69dbfa9ee80a95460beeb1",
    "skills/lead/scripts/check-git-push-gate.ps1": "fcd84f421232d527cc1571526ae55bc6211704ae72eebac42a6610fbf957fcc7",
    "skills/lead/scripts/check-bugfix-discipline.ps1": "fd1d32ccfeda15ec28be7808f9d0575a438b07a040aa570377704fd18167ac21",
    "skills/lead/scripts/agents-mode-reminder.ps1": "a8e078e98b623a8dda5b881994c120d785231ffb8a5a63f6717cc2ccb58af50f",
    "skills/lead/scripts/agent-run-ledger.ps1": "5a621a4ff2f93e853c77d9c9eebc3da6dc1cad59161d9028fe944e79d50f2e66",
    "skills/lead/scripts/check-work-items-state.ps1": "7c6ee275f9ebd80a0aba682fbf30e1b447f7962185d5fe21c5d5247c876ba51c",
    "skills/lead/scripts/validate-work-item-state.ps1": "8ce49efc853b207773c966bc3bb55d6befef6b8e78fdb8151ef473f5f1377449",
    "skills/lead/hooks/check-stale-relation-residue.ps1": "6bcfabf9aff4da1542e166cb1de29408c5c9aaf2b9e1f89b9ca40fdc7d5647ef",
    "skills/lead/hooks/check-repository-orientation.ps1": "08e502dde3f5a4fa009ba904c5ce7a0e9c92cbcd436e1c1dfba453a5849ee6bd",
    "skills/lead/hooks/check-no-trash-in-repo.ps1": "c1d804b132b9aaa57f5ed42e29895ef0957d3f5671adc719a9599e49bebabd54",
    "skills/lead/hooks/check-mcp-momentum.ps1": "e75eada981c2d8dab78213fc276b4cae5022fed0ffc63ed70ad6f7697c8d5fc9",
    "skills/lead/hooks/check-machine-local-path.ps1": "0c9b3fb81fab87f773dcfc90d04bd1e6134e249e22824da3567a9d88d17ee0e5",
}
_CLAUDE_RETIRED_PS1 = {
    "agents/hooks/check-mcp-momentum.py": "4f3fe9eabe5ea4c8654bf554a271904b9fdb16d4e9de916b7058c953e02fa430",
    "agents/scripts/validate-skill-pack.ps1": "2a7c3b096d924db39bd4685852e0748b820f4b8b8fe7a037bf18eb20a35fae8f",
    "agents/scripts/turn-anchor-reminder.ps1": "edf6aef1861337d3cda0dc142c64bb28ed797c48670a379c4ca0a51a0f8d58d0",
    "agents/scripts/mcp-usage-reminder.ps1": "62c9990f57ee7eccadcf1504a638ff6cbe4b61548405288d70ed192254b54d3d",
    "agents/scripts/invoke-codex-prompt.ps1": "a6c8a2af483c5c4142586924d8b702b10eea89182aea0d6895a84d87f7bed392",
    "agents/scripts/invoke-claude-prompt.ps1": "e2a9d6316f5611b733745c20abea961c12bb8141949df6c3569763d5a7a9280d",
    "agents/scripts/invoke-claude-api.ps1": "7da6b460335609f023fdf4b115c960ef11d3425924d936baf721583930fc35ec",
    "agents/scripts/check-work-items-archival-stop.ps1": "16d7cc086c34ddd8b571ad1b0e926afd74114e88d0b80a4c422c2ec2875e82ae",
    "agents/scripts/check-work-items-archival-stop.py": "6fd48cbfb64e0861a5f8ad6c2c011fa6ae9dfd8567b1636dc2cf6b1ab18e11a1",
    "agents/scripts/check-work-items-archival-stop.sh": "3c5dbc2499b6694859c71b2478e49f92b9fe45369d5287ea16463bacf6f84628",
    "agents/scripts/check-scratch-valuables.ps1": "1aa910d0557bfc1abedd65d7c3e30c53bab4fc7147dbc453199ec60f37ec0b22",
    "agents/scripts/check-publication-safety.ps1": "0e0b8b9a41140a58a82e59d4a21bca59b9922952872613819995c31036a3b3df",
    "agents/scripts/check-passive-polling-stop.ps1": "04790e77b1c08d0d38767030531008739b9550664f69dbfa9ee80a95460beeb1",
    "agents/scripts/check-git-push-gate.ps1": "fcd84f421232d527cc1571526ae55bc6211704ae72eebac42a6610fbf957fcc7",
    "agents/scripts/check-bugfix-discipline.ps1": "fd1d32ccfeda15ec28be7808f9d0575a438b07a040aa570377704fd18167ac21",
    "agents/scripts/await-codex-dispatch.ps1": "b4a716397140bb3eada621666b7f1815f3d8eff1c54c8eb55ebd80a0b1121ae8",
    "agents/scripts/agents-mode-reminder.ps1": "1a2b89d39e6667a0189ad9182ee71f13e87ccbb1af45b0adb696a10b6ecbb543",
    "agents/scripts/agent-run-ledger.ps1": "5a621a4ff2f93e853c77d9c9eebc3da6dc1cad59161d9028fe944e79d50f2e66",
    "agents/scripts/check-work-items-state.ps1": "7c6ee275f9ebd80a0aba682fbf30e1b447f7962185d5fe21c5d5247c876ba51c",
    "agents/scripts/validate-work-item-state.ps1": "8ce49efc853b207773c966bc3bb55d6befef6b8e78fdb8151ef473f5f1377449",
    "agents/hooks/check-typed-routing.ps1": "b04b8fa8196e3909cf8eb2ae651df7fd629b356ed08488772ca4f9ee8b8f0a47",
    "agents/hooks/check-stale-relation-residue.ps1": "6bcfabf9aff4da1542e166cb1de29408c5c9aaf2b9e1f89b9ca40fdc7d5647ef",
    "agents/hooks/check-repository-orientation.ps1": "08e502dde3f5a4fa009ba904c5ce7a0e9c92cbcd436e1c1dfba453a5849ee6bd",
    "agents/hooks/check-no-trash-in-repo.ps1": "c1d804b132b9aaa57f5ed42e29895ef0957d3f5671adc719a9599e49bebabd54",
    "agents/hooks/check-mcp-momentum.ps1": "e75eada981c2d8dab78213fc276b4cae5022fed0ffc63ed70ad6f7697c8d5fc9",
    "agents/hooks/check-machine-local-path.ps1": "0c9b3fb81fab87f773dcfc90d04bd1e6134e249e22824da3567a9d88d17ee0e5",
}

# Python is the sole hook and reminder implementation owner.  Upgrade cleanup
# removes only the exact source-pack copies retired by that migration; a local
# customization stays untouched for the operator to resolve deliberately.
_CODEX_RETIRED_SH = {
    "hooks/check-machine-local-path.sh": "7856238ed5fbadaf10b9587ce8ebbf28cd4333cde57b95edebb288a4da6a7a68",
    "hooks/check-mcp-momentum.sh": "8f88b363f6c7f9df4c39d1d7d0c30b95d2540109323f1945af625552f0c3e5a4",
    "hooks/check-no-trash-in-repo.sh": "a2f1182711477842d8ce76db7c19866b89bdc8669a1da01a56c7c8338460c0c7",
    "hooks/check-repository-orientation.sh": "f3761535fe4558659a501979a62fc4a1435daa34d74fc41a0fb50b8aff0797e1",
    "hooks/check-stale-relation-residue.sh": "c32e8e4fc87f008f205c24f71f3dbc84b2e0ee900ff64bf62427d9bb2f687158",
    "scripts/agents-mode-reminder.sh": "e8b61f672d3b0563f913c166c8d3ed32bf19018423276dde8a600b40462e17e7",
    "scripts/check-bugfix-discipline.sh": "9ab0c1a4fca2673f19ddf6b1877e95dc35a6beb6c469d7b205a9959c6d5265d9",
    "scripts/check-git-push-gate.sh": "3bbe51e762508d5b2f7f40e2cee7f06e5c8f0a7bf680115fa0ff448c5d4d3938",
    "scripts/check-passive-polling-stop.sh": "16e4a601db6ac62a2bfa38a3391ec434e632858f904be730782b6b7a3982ae06",
    "scripts/check-scratch-valuables.sh": "3b1fca32c89cd68dfbbb6adea5d636ef49b5091220a689e593a6e7212616a065",
    "scripts/mcp-usage-reminder.sh": "f3e56c8a05aafcd0dce9905b40ab042df4edf40968d6dfda46d70a38e5351d0d",
    "scripts/turn-anchor-reminder.sh": "f0036ab9dd1fda1b9b7479f27f4585de9d5146bbd2a4bec10b4c4468f612c21e",
}
_CLAUDE_RETIRED_SH = {
    "hooks/check-machine-local-path.sh": "7856238ed5fbadaf10b9587ce8ebbf28cd4333cde57b95edebb288a4da6a7a68",
    "hooks/check-mcp-momentum.sh": "8f88b363f6c7f9df4c39d1d7d0c30b95d2540109323f1945af625552f0c3e5a4",
    "hooks/check-no-trash-in-repo.sh": "a2f1182711477842d8ce76db7c19866b89bdc8669a1da01a56c7c8338460c0c7",
    "hooks/check-repository-orientation.sh": "f3761535fe4558659a501979a62fc4a1435daa34d74fc41a0fb50b8aff0797e1",
    "hooks/check-stale-relation-residue.sh": "c32e8e4fc87f008f205c24f71f3dbc84b2e0ee900ff64bf62427d9bb2f687158",
    "hooks/check-typed-routing.sh": "eaa46aaf345be0bd4bcc89b1d3a3f961da3a20c9e18e19d3963fc29bc41bb10b",
    "scripts/agents-mode-reminder.sh": "e70818e01d0ff38bae2b7e96e4ac501e13e90a762672bb812309689e6ecbe096",
    "scripts/check-bugfix-discipline.sh": "9ab0c1a4fca2673f19ddf6b1877e95dc35a6beb6c469d7b205a9959c6d5265d9",
    "scripts/check-git-push-gate.sh": "3bbe51e762508d5b2f7f40e2cee7f06e5c8f0a7bf680115fa0ff448c5d4d3938",
    "scripts/check-passive-polling-stop.sh": "16e4a601db6ac62a2bfa38a3391ec434e632858f904be730782b6b7a3982ae06",
    "scripts/check-scratch-valuables.sh": "3b1fca32c89cd68dfbbb6adea5d636ef49b5091220a689e593a6e7212616a065",
    "scripts/mcp-usage-reminder.sh": "f3e56c8a05aafcd0dce9905b40ab042df4edf40968d6dfda46d70a38e5351d0d",
    "scripts/turn-anchor-reminder.sh": "f0036ab9dd1fda1b9b7479f27f4585de9d5146bbd2a4bec10b4c4468f612c21e",
}


def _parser(provider: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=f"Install the production {provider} pack.")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--global", "-Global", dest="global_install", action="store_true")
    modes.add_argument("--target", "-Target")
    parser.add_argument("--force", "-Force", action="store_true")
    parser.add_argument("--dry-run", "-DryRun", action="store_true")
    parser.add_argument("--allow-unsafe-target", "-AllowUnsafeTarget", action="store_true")
    parser.add_argument("--no-hypothesis-hook", "-NoHypothesisHook", action="store_true")
    return parser


def _repo_root(script: Path) -> Path:
    return script.resolve().parent.parent


def _git_root() -> Path:
    proc = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return Path(proc.stdout.strip()).resolve() if proc.returncode == 0 else Path.cwd().resolve()


def _contains_reparse(path: Path) -> bool:
    current = path
    while True:
        if current.exists() or current.is_symlink():
            if current.is_symlink():
                return True
            attrs = getattr(current.stat(follow_symlinks=False), "st_file_attributes", 0)
            if attrs & getattr(__import__("stat"), "FILE_ATTRIBUTE_REPARSE_POINT", 0):
                return True
        if current.parent == current:
            return False
        current = current.parent


def _minimal_transaction_roots(paths: list[Path]) -> tuple[Path, ...]:
    roots: list[Path] = []
    for candidate in sorted(
        {Path(os.path.abspath(path)) for path in paths},
        key=lambda path: (len(path.parts), os.path.normcase(str(path))),
    ):
        if any(candidate == root or root in candidate.parents for root in roots):
            continue
        roots.append(candidate)
    return tuple(roots)


def _resolve_write_through_symlink(path: Path) -> Path:
    current = Path(os.path.abspath(path))
    seen: set[str] = set()
    while True:
        key = os.path.normcase(str(current))
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            return current
        except OSError as exc:
            raise ValueError(
                f"cannot resolve transaction symlink {path}: {exc}"
            ) from exc
        if not stat.S_ISLNK(mode):
            if stat.S_ISDIR(mode):
                raise ValueError(
                    f"transaction symlink resolves to a directory: {path} -> {current}"
                )
            return current
        if key in seen:
            raise ValueError(f"transaction symlink cycle detected at {current}")
        seen.add(key)
        try:
            target = Path(os.readlink(current))
        except OSError as exc:
            raise ValueError(
                f"cannot read transaction symlink {current}: {exc}"
            ) from exc
        current = Path(
            os.path.abspath(
                target if target.is_absolute() else current.parent / target
            )
        )


def _transaction_snapshot_paths(paths: tuple[Path, ...]) -> tuple[Path, ...]:
    expanded = list(paths)
    for path in paths:
        try:
            mode = path.lstat().st_mode
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ValueError(
                f"cannot inspect transaction path {path}: {exc}"
            ) from exc
        if stat.S_ISLNK(mode):
            expanded.append(_resolve_write_through_symlink(path))
    return _minimal_transaction_roots(expanded)


class _InstallTransaction:
    """Snapshot the coherent install surface and restore it unless committed."""

    def __init__(self, paths: list[Path], *, enabled: bool) -> None:
        self.paths = tuple(
            sorted(
                {Path(os.path.abspath(path)) for path in paths},
                key=lambda path: (len(path.parts), os.path.normcase(str(path))),
            )
        )
        self.enabled = enabled
        self.committed = False
        self._temporary: tempfile.TemporaryDirectory[str] | None = None
        self._entries: list[dict[str, object]] = []
        self._absent_parents: set[Path] = set()

    def __enter__(self) -> "_InstallTransaction":
        if not self.enabled:
            return self
        self.paths = _transaction_snapshot_paths(self.paths)
        self._temporary = tempfile.TemporaryDirectory(
            prefix="orchestrarium-install-transaction-"
        )
        backup_root = Path(self._temporary.name)
        try:
            for index, path in enumerate(self.paths):
                parent = path.parent
                while (
                    parent != parent.parent
                    and not parent.exists()
                    and not parent.is_symlink()
                ):
                    self._absent_parents.add(parent)
                    parent = parent.parent
                backup = backup_root / str(index)
                if path.is_symlink():
                    self._entries.append(
                        {
                            "path": path,
                            "kind": "symlink",
                            "target": os.readlink(path),
                            "target_is_directory": path.is_dir(),
                        }
                    )
                elif path.is_file():
                    shutil.copy2(path, backup)
                    self._entries.append(
                        {"path": path, "kind": "file", "backup": backup}
                    )
                elif path.is_dir():
                    shutil.copytree(path, backup, symlinks=True)
                    self._entries.append(
                        {"path": path, "kind": "directory", "backup": backup}
                    )
                else:
                    self._entries.append({"path": path, "kind": "absent"})
        except BaseException:
            self._temporary.cleanup()
            self._temporary = None
            raise
        return self

    @staticmethod
    def _remove_current(path: Path) -> None:
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)

    def _restore(self) -> None:
        for entry in self._entries:
            path = entry["path"]
            assert isinstance(path, Path)
            self._remove_current(path)
            kind = entry["kind"]
            if kind == "absent":
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            if kind == "file":
                backup = entry["backup"]
                assert isinstance(backup, Path)
                shutil.copy2(backup, path)
            elif kind == "directory":
                backup = entry["backup"]
                assert isinstance(backup, Path)
                shutil.copytree(backup, path, symlinks=True)
            else:
                path.symlink_to(
                    entry["target"],
                    target_is_directory=bool(entry["target_is_directory"]),
                )
        for parent in sorted(
            self._absent_parents,
            key=lambda item: len(item.parts),
            reverse=True,
        ):
            if parent.is_symlink():
                continue
            try:
                parent.rmdir()
            except (FileNotFoundError, OSError):
                pass

    def commit(self) -> None:
        self.committed = True

    def __exit__(self, exc_type, _exc, _traceback) -> bool:
        if not self.enabled:
            return False
        try:
            if exc_type is not None or not self.committed:
                self._restore()
        finally:
            assert self._temporary is not None
            self._temporary.cleanup()
            self._temporary = None
        return False


def _target(provider: str, args: argparse.Namespace) -> tuple[str, Path, Path | None]:
    suffix = f".{provider}"
    if args.global_install:
        mode = "global"
        home = Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or "")
        if not str(home):
            raise ValueError("cannot resolve the user home directory")
        target = home.expanduser() / suffix
        project = None
    elif args.target:
        mode = "target"
        raw = Path(os.path.expandvars(os.path.expanduser(args.target)))
        target = raw if raw.name.casefold() == suffix else raw / suffix
        project = target.parent
    else:
        mode = "repo"
        project = _git_root()
        target = project / suffix
    target = target.resolve(strict=False)
    if mode != "global":
        project = target.parent
    if _contains_reparse(target):
        raise ValueError(f"refusing reparse-point target path: {target}")
    if target.name.casefold() != suffix:
        raise ValueError(f"target must resolve to a {suffix} directory")
    if mode == "target" and not args.allow_unsafe_target:
        raise ValueError("unsafe custom target denied; use --allow-unsafe-target to override")
    return mode, target, project


def _copy_file(source: Path, target: Path, dry_run: bool) -> None:
    if dry_run:
        print(f"    [dry-run] would copy {source} -> {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _sync_tree(source: Path, target: Path, dry_run: bool) -> None:
    for item in sorted(source.rglob("*")):
        relative = item.relative_to(source)
        if "__pycache__" in relative.parts or item.suffix.casefold() == ".ps1":
            continue
        destination = target / relative
        if item.is_file():
            _copy_file(item, destination, dry_run)


def _sync_file_destinations(source: Path, target: Path) -> list[Path]:
    destinations: list[Path] = []
    for item in sorted(source.rglob("*")):
        relative = item.relative_to(source)
        if (
            item.is_file()
            and item.suffix.casefold() != ".ps1"
            and "__pycache__" not in relative.parts
        ):
            destinations.append(target / relative)
    return destinations


def _installer_mutation_paths(
    *,
    provider: str,
    source: Path,
    target: Path,
    agents_root: Path,
    docs_target: Path,
    source_tree: Path,
    target_tree: Path,
    mode_target: Path,
    registration: Path,
    shared_mode_target: Path | None,
) -> list[Path]:
    """Return only paths whose contents this installer can mutate."""
    if provider not in {"codex", "claude"}:
        raise ValueError(f"unsupported provider: {provider}")

    paths: list[Path] = []
    if provider == "codex":
        paths.extend(_sync_file_destinations(source_tree, target_tree))
        paths.extend(
            target / "agents" / source_file.name
            for source_file in sorted((source / "agents").glob("*.toml"))
        )
        helper_target = target_tree / "lead" / "scripts"
        retired_root = agents_root
        retired_manifest = _CODEX_RETIRED_PS1
    else:
        for directory in ("agents", "commands", "skills"):
            paths.extend(
                _sync_file_destinations(
                    source / directory,
                    target / directory,
                )
            )
        paths.extend(_claude_stale_namespace_paths(source, target))
        paths.append(target / "AGENTS.md")
        helper_target = target / "agents" / "scripts"
        retired_root = target
        retired_manifest = _CLAUDE_RETIRED_PS1

    paths.extend(
        helper_target / helper
        for helper in RUNTIME_HELPERS
    )
    if provider == "codex":
        paths.extend(helper_target / helper for helper in CODEX_RUNTIME_HELPERS)
        paths.append(helper_target / CODEX_HOOK_INVENTORY)
    paths.extend(
        (
            docs_target,
            mode_target,
            mode_target.with_suffix(""),
            registration,
        )
    )
    if shared_mode_target is not None:
        paths.extend(
            (
                shared_mode_target,
                shared_mode_target.with_suffix(""),
            )
        )
    paths.extend(retired_root / Path(relative) for relative in retired_manifest)
    return paths


def _normalize_agents_mode(
    root: Path, template: Path, target: Path, provider: str, dry_run: bool
) -> None:
    legacy = target.with_suffix("")
    if legacy.is_file() and not target.exists():
        print(f"  Migrating legacy .agents-mode to {target}...")
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            legacy.replace(target)
    if dry_run:
        print(f"    [dry-run] would normalize {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    proc = _run(
        [
            str(root / "scripts" / "normalize-agents-mode.py"),
            "--template",
            str(template),
            "--target",
            str(target),
            "--provider",
            provider,
        ],
        cwd=root,
    )
    if proc.returncode:
        raise RuntimeError(f"agents-mode normalization failed for {target}")


def _normalize_agent_override(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.rstrip("\n")


def _agent_override_sha256(text: str) -> str:
    normalized = _normalize_agent_override(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _reclaim_codex_presets(source: Path, target: Path, dry_run: bool) -> None:
    removed = False
    for source_file in sorted(source.glob("*.toml")):
        installed = target / source_file.name
        if not installed.is_file():
            continue
        actual = _normalize_agent_override(installed.read_text(encoding="utf-8"))
        current = _normalize_agent_override(source_file.read_text(encoding="utf-8"))
        historical = HISTORICAL_CODEX_AGENT_SHA256.get(
            source_file.name, frozenset()
        )
        if actual == current or _agent_override_sha256(actual) in historical:
            print(f"  Removing retired pack-owned built-in agent override {source_file.name}...")
            if not dry_run:
                installed.unlink()
                removed = True
        else:
            print(f"  Preserving existing custom built-in agent override {source_file.name}...")
    if removed and target.is_dir() and not any(target.iterdir()):
        target.rmdir()


def _claude_stale_namespace_paths(source: Path, target: Path) -> tuple[Path, ...]:
    candidates: list[Path] = []
    for directory, pattern, expected_kind in (
        ("commands", "agents-*.md", "file"),
        ("skills", "agents-*", "directory"),
    ):
        source_dir = source / directory
        target_dir = target / directory
        if not target_dir.is_dir():
            continue
        for installed in sorted(target_dir.glob(pattern)):
            if (source_dir / installed.name).exists():
                continue
            if installed.is_symlink():
                candidates.append(installed)
            elif expected_kind == "file" and installed.is_file():
                candidates.append(installed)
            elif expected_kind == "directory" and installed.is_dir():
                candidates.append(installed)
    return tuple(candidates)


def _reclaim_claude_namespace(source: Path, target: Path, dry_run: bool) -> None:
    for installed in _claude_stale_namespace_paths(source, target):
        relative = installed.relative_to(target).as_posix()
        if dry_run:
            print(f"    [dry-run] would reclaim stale pack namespace: {relative}")
            continue
        if installed.is_symlink() or installed.is_file():
            installed.unlink()
        else:
            shutil.rmtree(installed)
        print(f"  Reclaimed stale pack item: {relative}")


def _merge_codex_agents(root: Path, source: Path, target: Path, dry_run: bool) -> None:
    pack = (
        CODEX_BEGIN
        + "\n"
        + (root / "shared" / "AGENTS.shared.md").read_text(encoding="utf-8").rstrip()
        + "\n\n"
        + (source / "AGENTS.codex.md").read_text(encoding="utf-8").rstrip()
        + "\n"
        + CODEX_END
        + "\n"
    )
    if target.is_file():
        existing = target.read_text(encoding="utf-8")
        if CODEX_BEGIN in existing and CODEX_END in existing:
            start = existing.index(CODEX_BEGIN)
            end = existing.index(CODEX_END, start) + len(CODEX_END)
            content = existing[:start] + pack.rstrip("\n") + existing[end:]
        elif "# Shared Governance" in existing or "# Codex Platform Rules" in existing:
            starts = [
                position
                for marker in ("# Shared Governance", "# Codex Platform Rules", "# Default Delegation Rule")
                if (position := existing.find(marker)) >= 0
            ]
            start = min(starts)
            policy = existing.find("## Project policies", start)
            content = existing[:start] + pack + (existing[policy:] if policy >= 0 else "")
        else:
            content = pack + "\n" + existing
    else:
        content = pack
    if dry_run:
        print(f"    [dry-run] would merge {target}")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")


def _merge_claude_docs(root: Path, source: Path, target: Path, dry_run: bool) -> None:
    claude_source = (source / "CLAUDE.md").read_text(encoding="utf-8")
    if target.is_file():
        existing = target.read_text(encoding="utf-8")
        starts = [
            position
            for marker in ("\n@AGENTS.md", "\n# Claude Code Pack", "\n# Claudestrator")
            if (position := ("\n" + existing).find(marker)) >= 0
        ]
        content = existing[: min(starts)] + claude_source if starts else claude_source + "\n" + existing
    else:
        content = claude_source
    shared = (root / "shared" / "AGENTS.shared.md").read_text(encoding="utf-8")
    agents_target = target.parent / "AGENTS.md"
    if dry_run:
        print(f"    [dry-run] would merge {target} and {agents_target}")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
        if agents_target.is_file() and "# Shared Governance" not in agents_target.read_text(encoding="utf-8"):
            shared = shared.rstrip() + "\n\n" + agents_target.read_text(encoding="utf-8")
        agents_target.write_text(shared, encoding="utf-8", newline="\n")


def _run(arguments: list[str], cwd: Path, *, capture: bool = False) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, *arguments],
        cwd=cwd,
        env=env,
        capture_output=capture,
        text=capture,
        encoding="utf-8" if capture else None,
        errors="replace" if capture else None,
    )


_HOOK_METADATA = (
    ("check-bugfix-discipline", "scripts", "PreToolUse", "Edit|Write|NotebookEdit|apply_patch"),
    ("check-git-push-gate", "scripts", "PreToolUse", "Bash|PowerShell"),
    ("check-passive-polling-stop", "scripts", "Stop", None),
    ("check-machine-local-path", "hooks", "PreToolUse", "Edit|Write|NotebookEdit|apply_patch"),
    ("check-no-trash-in-repo", "hooks", "PreToolUse", "Edit|Write|NotebookEdit|apply_patch|Bash|PowerShell"),
    ("check-stale-relation-residue", "hooks", "PreToolUse", "Edit|Write|NotebookEdit|apply_patch"),
    ("check-repository-orientation", "hooks", "PreToolUse", "Edit|Write|NotebookEdit|apply_patch|Bash|PowerShell|shell_command|exec_command"),
    ("check-mcp-momentum", "hooks", "PreToolUse", "Grep|Bash|PowerShell|shell_command|exec_command"),
    ("mcp-usage-reminder", "scripts", "SessionStart", None),
    ("check-typed-routing", "hooks", "PreToolUse", "Agent"),
    ("agents-mode-reminder", "scripts", "SessionStart", None),
    ("check-scratch-valuables", "scripts", "SessionStart", None),
    ("turn-anchor-reminder", "scripts", "UserPromptSubmit", None),
)

_HOOK_DIRECTORY_OVERRIDES = {
    ("claude", "check-mcp-momentum"): "scripts",
}


def _universal_hook_manifest_module():
    path = Path(__file__).with_name("universal_hooks_manifest.py")
    spec = importlib.util.spec_from_file_location("orchestrarium_universal_hook_manifest", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load universal hook manifest: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _hook_specs(provider: str, installed_root: Path):
    scripts = installed_root / "scripts"
    hooks = installed_root / "hooks"
    membership = _universal_hook_manifest_module().registered_hook_stems(provider)
    metadata = {stem: (directory, event, matcher) for stem, directory, event, matcher in _HOOK_METADATA}
    missing = sorted(membership.difference(metadata))
    if missing:
        raise RuntimeError("registered hook metadata is missing for: " + ", ".join(missing))
    roots = {"scripts": scripts, "hooks": hooks}
    specs = [
        (
            stem,
            roots[_HOOK_DIRECTORY_OVERRIDES.get((provider, stem), directory)]
            / f"{stem}.py",
            event,
            matcher,
        )
        for stem, directory, event, matcher in _HOOK_METADATA
        if stem in membership
    ]
    if len(specs) != len(membership):
        raise RuntimeError("registered hook membership did not resolve uniquely")
    return specs


def _hook_health_module(root: Path):
    path = root / "scripts" / "check-hook-health.py"
    spec = importlib.util.spec_from_file_location("orchestrarium_hook_health", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load hook health helper: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RETIRED_HOOK_SPECS = (
    ("check-work-items-archival-stop", "Stop"),
)


def _install_hooks(
    root: Path,
    provider: str,
    registration: Path,
    installed_root: Path,
    mode: str,
) -> None:
    installer = root / "scripts" / "install-hypothesis-hook.py"
    host = "windows" if os.name == "nt" else "posix"
    base = [
        str(installer),
        "--target",
        str(registration),
        "--platform",
        provider,
        "--host-os",
        host,
    ]
    preflight = _run(
        [
            str(installer),
            "--target",
            str(registration),
            "--platform",
            provider,
            "--repo-root",
            str(root),
            "--test-install-scope",
            mode,
            "--test-transaction-preflight",
        ],
        root,
    )
    if preflight.returncode:
        raise RuntimeError("hook transaction preflight failed")
    for _marker, script, _event, _matcher in _hook_specs(provider, installed_root):
        proc = _run([*base, "--script-path", str(script), "--validate-only"], root)
        if proc.returncode:
            raise RuntimeError(f"hook target preflight failed for {script}")
    _checkpoint(root, installer, registration, provider, mode, "sync")
    for marker, event in RETIRED_HOOK_SPECS:
        proc = _run(
            [
                *base,
                "--script-marker",
                marker,
                "--hook-event",
                event,
                "--remove",
            ],
            root,
        )
        if proc.returncode:
            raise RuntimeError(f"obsolete hook removal failed for {marker}")
    health_module = _hook_health_module(root) if provider == "codex" else None
    codex_command = (
        health_module.resolve_codex_command(os.environ.get("CODEX_BIN"))
        if health_module is not None
        else None
    )
    inventory_path = installed_root / "scripts" / CODEX_HOOK_INVENTORY
    if health_module is not None:
        manifest_stems = health_module._manifest_stems(root, "codex")
        spec_stems = {marker for marker, *_rest in _hook_specs(provider, installed_root)}
        if manifest_stems != spec_stems:
            raise RuntimeError("Codex hook specifications drifted from universal manifest")
    before_identities = (
        health_module.owned_canonical_identities(
            target=registration,
            platform=provider,
            host_os=host,
            repo_root=root,
        )
        if health_module is not None and registration.is_file()
        else set()
    )
    for marker, script, event, matcher in _hook_specs(provider, installed_root):
        arguments = [*base, "--script-marker", marker, "--script-path", str(script)]
        if event != "PreToolUse":
            arguments.extend(["--hook-event", event])
        if matcher:
            arguments.extend(["--tool-matcher", matcher])
        proc = _run(arguments, root)
        if proc.returncode:
            raise RuntimeError(f"hook registration failed for {marker}")
    _checkpoint(root, installer, registration, provider, mode, "register")
    touched_identities = (
        health_module.owned_canonical_identities(
            target=registration,
            platform=provider,
            host_os=host,
            repo_root=root,
        )
        - before_identities
        if health_module is not None
        else set()
    )
    if health_module is not None:
        health_module.write_codex_inventory(
            target=registration,
            specs=_hook_specs(provider, installed_root),
            inventory_path=inventory_path,
            host_os=host,
        )
    health_arguments = [
        str(root / "scripts" / "check-hook-health.py"),
        "--target",
        str(registration),
        "--platform",
        provider,
        "--host-os",
        host,
        "--repo-root",
        str(root),
    ]
    if provider == "codex":
        assert codex_command is not None
        health_arguments.extend(
            [
                "--codex-trust-mode",
                "report",
                "--inventory",
                str(inventory_path),
                "--codex-command-json",
                json.dumps(codex_command),
                "--codex-home",
                str(registration.parent.resolve()),
                "--query-cwd",
                str(root.resolve()),
            ]
        )
        for identity in sorted(touched_identities):
            health_arguments.extend(["--touched-identity", identity])
    health = _run(
        health_arguments,
        root,
    )
    if health.returncode:
        raise RuntimeError("hook target verification failed")
    _checkpoint(root, installer, registration, provider, mode, "verify")
    _checkpoint(root, installer, registration, provider, mode, "reclaim")
    if provider == "codex":
        installed_health = _run(
            [
                str(installed_root / "scripts" / "check-hook-health.py"),
                "--target",
                str(registration),
                "--platform",
                "codex",
                "--host-os",
                host,
                "--inventory",
                str(inventory_path),
                "--codex-trust-mode",
                "report",
                "--codex-command-json",
                json.dumps(codex_command),
                "--codex-home",
                str(registration.parent.resolve()),
                "--query-cwd",
                str(root.resolve()),
                *[
                    item
                    for identity in sorted(touched_identities)
                    for item in ("--touched-identity", identity)
                ],
            ],
            root,
        )
        if installed_health.returncode:
            raise RuntimeError("post-reclaim installed hook verification failed")


def _checkpoint(
    root: Path,
    installer: Path,
    registration: Path,
    provider: str,
    mode: str,
    stage: str,
) -> None:
    proc = _run(
        [
            str(installer),
            "--target",
            str(registration),
            "--platform",
            provider,
            "--repo-root",
            str(root),
            "--test-install-scope",
            mode,
            "--test-transaction-checkpoint",
            stage,
        ],
        root,
    )
    if proc.returncode:
        raise RuntimeError(f"hook transaction checkpoint failed at {stage}")


def _reclaim_retired(target_root: Path, manifest: dict[str, str], dry_run: bool) -> None:
    for relative, expected in manifest.items():
        path = target_root / Path(relative)
        if not path.is_file():
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual == expected:
            print(f"  Reclaiming unchanged retired pack file: {relative}")
            if not dry_run:
                path.unlink()
        else:
            print(f"  Preserving customized retired pack file: {relative}")


def _verify_files(
    source: Path,
    target: Path,
    reclaimed_hook_stems: set[str],
) -> list[str]:
    missing: list[str] = []
    for item in source.rglob("*"):
        relative = item.relative_to(source)
        reclaimed_shell = (
            item.suffix.casefold() == ".sh"
            and item.stem in reclaimed_hook_stems
        )
        if (
            item.is_file()
            and item.suffix.casefold() != ".ps1"
            and "__pycache__" not in relative.parts
            and not reclaimed_shell
        ):
            if not (target / relative).is_file():
                missing.append(str(relative))
    return missing


def install(provider: str, argv: list[str] | None = None) -> int:
    args = _parser(provider).parse_args(argv)
    script = Path(__file__)
    root = _repo_root(script)
    source = root / f"src.{provider}"
    try:
        mode, target, project = _target(provider, args)
        if provider == "codex":
            agents_root = target if mode == "global" else project / ".agents"
            skills_target = agents_root / "skills"
            docs_target = target / "AGENTS.md" if mode == "global" else project / "AGENTS.md"
            installed_hook_root = skills_target / "lead"
            registration = target / "hooks.json"
            source_tree = source / "skills"
            target_tree = skills_target
            mode_target = agents_root / ".agents-mode.yaml"
            normalize_provider = "codex"
        else:
            agents_root = target
            docs_target = target / "CLAUDE.md"
            installed_hook_root = target / "agents"
            registration = target / "settings.json"
            source_tree = source
            target_tree = target
            mode_target = target / ".agents-mode.yaml"
            normalize_provider = "shared"
        shared_mode_target: Path | None = None
        if mode == "global":
            home = Path(
                os.environ.get("USERPROFILE") or os.environ.get("HOME") or ""
            ).expanduser()
            shared_mode_target = home / ".agents-mode.yaml"

        print(f"=== {provider.capitalize()} Python Installer ===")
        print(f"Source: {source}")
        print(f"Target: {target}")
        print(f"Mode: {mode}")
        if args.dry_run:
            print("Mode: dry-run")

        transaction_paths = _installer_mutation_paths(
            provider=provider,
            source=source,
            target=target,
            agents_root=agents_root,
            docs_target=docs_target,
            source_tree=source_tree,
            target_tree=target_tree,
            mode_target=mode_target,
            registration=registration,
            shared_mode_target=shared_mode_target,
        )
        transaction = _InstallTransaction(
            transaction_paths,
            enabled=not args.dry_run,
        )
        with transaction:
            if provider == "codex":
                _sync_tree(source_tree, target_tree, args.dry_run)
            else:
                for directory in ("agents", "commands", "skills"):
                    _sync_tree(source / directory, target / directory, args.dry_run)
            helper_target = (
                skills_target / "lead" / "scripts"
                if provider == "codex"
                else target / "agents" / "scripts"
            )
            for helper in RUNTIME_HELPERS:
                _copy_file(
                    root / "scripts" / helper,
                    helper_target / helper,
                    args.dry_run,
                )
            if provider == "codex":
                for helper in CODEX_RUNTIME_HELPERS:
                    _copy_file(
                        root / "scripts" / helper,
                        helper_target / helper,
                        args.dry_run,
                    )

            if provider == "codex":
                _reclaim_codex_presets(
                    source / "agents", target / "agents", args.dry_run
                )
                _merge_codex_agents(root, source, docs_target, args.dry_run)
            else:
                _reclaim_claude_namespace(source, target, args.dry_run)
                _merge_claude_docs(root, source, docs_target, args.dry_run)
            _normalize_agents_mode(
                root,
                root / "shared" / "agents-mode.defaults.yaml",
                mode_target,
                normalize_provider,
                args.dry_run,
            )
            if shared_mode_target is not None:
                _normalize_agents_mode(
                    root,
                    root / "shared" / "agents-mode.defaults.yaml",
                    shared_mode_target,
                    "shared",
                    args.dry_run,
                )

            hooks_enabled = (
                not args.no_hypothesis_hook
                and not args.dry_run
                and not os.environ.get("ORCHESTRARIUM_NO_HYPOTHESIS_HOOK")
            )
            if hooks_enabled:
                _install_hooks(
                    root, provider, registration, installed_hook_root, mode
                )

            _reclaim_retired(
                target if provider == "claude" else agents_root,
                (
                    {**_CLAUDE_RETIRED_PS1, **_CLAUDE_RETIRED_SH}
                    if provider == "claude"
                    else {**_CODEX_RETIRED_PS1, **_CODEX_RETIRED_SH}
                ),
                args.dry_run,
            )
            if args.dry_run:
                print("RESULT: DRY-RUN complete (no files modified).")
                return 0

            missing = _verify_files(
                source_tree if provider == "codex" else source / "agents",
                target_tree if provider == "codex" else target / "agents",
                {
                    marker
                    for marker, *_rest in _hook_specs(
                        provider, installed_hook_root
                    )
                },
            )
            if missing:
                print(
                    f"RESULT: FAIL ({len(missing)} missing installed files)",
                    file=sys.stderr,
                )
                for item in missing:
                    print(f"  - {item}", file=sys.stderr)
                return 1
            if provider == "codex":
                missing_runtime = [
                    path
                    for path in (
                        helper_target / "check-hook-health.py",
                        helper_target / CODEX_HOOK_INVENTORY,
                    )
                    if not path.is_file()
                ]
                if missing_runtime:
                    print(
                        "RESULT: FAIL (Codex hook health runtime incomplete)",
                        file=sys.stderr,
                    )
                    return 1
            if not mode_target.is_file() or not docs_target.is_file():
                print(
                    "RESULT: FAIL (documentation or agents-mode output missing)",
                    file=sys.stderr,
                )
                return 1
            print(
                f"RESULT: OK - {provider.capitalize()} pack installed to {target}"
            )
            transaction.commit()
            return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
