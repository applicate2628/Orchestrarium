#!/usr/bin/env python3
"""Read-only validation for installed Orchestrarium hook registrations."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable


def _manifest_stems(repo_root: Path, platform: str) -> set[str]:
    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import universal_hooks_manifest as manifest

    if platform == "claude":
        specs = (
            ("scripts", "src.claude/agents/scripts", manifest.PACK_ONLY_SCRIPTS),
            ("hooks", "src.claude/agents/hooks", manifest.PACK_ONLY_HOOKS),
        )
    elif platform == "codex":
        specs = (
            ("scripts", "src.codex/skills/lead/scripts", manifest.PACK_ONLY_SCRIPTS),
            ("hooks", "src.codex/skills/lead/hooks", manifest.PACK_ONLY_HOOKS),
        )
    else:
        raise ValueError(f"unsupported platform: {platform}")

    stems: set[str] = set()
    for subdir, rel_dir, pack_only in specs:
        source_dir = repo_root / rel_dir
        owned = set(manifest.canon_names(repo_root, subdir)) | set(pack_only[rel_dir])
        for python_target in source_dir.glob("*.py"):
            if python_target.name not in owned:
                continue
            if (
                python_target.with_suffix(".ps1").is_file()
                or python_target.with_suffix(".sh").is_file()
            ):
                stems.add(python_target.stem)
    return stems


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"registration file does not exist: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"registration root is not an object: {path}")
    return data


def _split_windows_command(command: str) -> list[str]:
    return [
        token[1:-1].replace("''", "'")
        if len(token) >= 2 and token[0] == token[-1] and token[0] in {"'", '"'}
        else token
        for token in shlex.split(command, posix=False)
    ]


def _command_argv(hook: dict[str, Any], platform: str, host_os: str) -> list[str]:
    command = hook.get("command")
    if not isinstance(command, str) or not command:
        raise ValueError("hook command is missing")
    args = hook.get("args")
    if platform == "claude":
        if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
            raise ValueError("Claude hook args must be a string array")
        return [command, *args]
    if args is not None:
        raise ValueError("Codex hook entry unexpectedly contains args")
    return (
        _split_windows_command(command)
        if host_os == "windows"
        else shlex.split(command)
    )


def _iter_owned_hooks(
    data: dict[str, Any],
    stems: set[str],
    platform: str,
    host_os: str,
) -> Iterable[tuple[str, str, list[str]]]:
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        raise ValueError("'hooks' key is not an object")
    for event, entries in hooks.items():
        if not isinstance(entries, list):
            raise ValueError(f"hooks.{event} is not an array")
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            commands = entry.get("hooks")
            if not isinstance(commands, list):
                continue
            for command_hook in commands:
                if not isinstance(command_hook, dict):
                    continue
                # `_command_argv` enforces the exec shape this pack's own
                # installer writes (Claude: `command` plus a string-array
                # `args`). Third-party tools registering into the same
                # settings.json need not use that shape -- a real one on this
                # machine registers `{"command": "codegraph prompt-hook"}` with
                # no `args` at all, which is valid for the runtime and simply
                # not ours. Parsing used to run BEFORE the stem filter, so one
                # foreign entry failed the whole health check and reported the
                # operator's fully converted, working registration as broken.
                # An entry `_command_argv` cannot parse is NOT proof it was
                # never ours: a command-only entry with no `args` key -- the
                # exact shape a foreign tool is allowed to use -- also fails
                # to parse on the Claude platform even when its command
                # string names one of THIS pack's own manifest stems (e.g. a
                # mis-registered or hand-edited duplicate). Silently skipping
                # that entry would let it fire this pack's own hook a second
                # time without the duplicate check ever seeing it, because a
                # skipped entry never becomes a counted row. So an unparseable
                # entry is interrogated before it is skipped: the raw entry is
                # serialized and searched for an owned manifest stem. Naming
                # one is fatal (loud failure, naming the stem) precisely
                # because it cannot be verified as safe; naming none means it
                # cannot be ours and is skipped. This narrows what the checker
                # polices to what the pack installs -- it does not weaken any
                # check on an owned, parseable entry.
                try:
                    argv = _command_argv(command_hook, platform, host_os)
                except ValueError:
                    raw = json.dumps(command_hook)
                    named_stems = sorted(stem for stem in stems if stem in raw)
                    if named_stems:
                        raise ValueError(
                            "entry names owned hook stem(s) but could not be "
                            "parsed as this pack's exec shape: "
                            + ", ".join(named_stems)
                        )
                    continue
                joined = "\0".join(argv)
                matches = sorted(stem for stem in stems if stem in joined)
                if len(matches) == 1:
                    yield event, matches[0], argv


def _resolve_executable(value: str, host_os: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        if not candidate.is_file():
            raise ValueError(f"registered executable is missing: {candidate}")
        if host_os == "windows" and candidate.suffix.lower() != ".exe":
            raise ValueError(f"registered Windows executable is not a .exe: {candidate}")
        if host_os == "posix" and not os.access(candidate, os.X_OK):
            raise ValueError(f"registered executable is not executable: {candidate}")
        return candidate
    resolved = shutil.which(value)
    if not resolved:
        raise ValueError(f"registered wrapper executable is unavailable: {value}")
    return Path(resolved)


def _target_path(argv: list[str]) -> Path | None:
    for raw in reversed(argv[1:]):
        value = raw.strip("'\"")
        candidate = Path(value)
        if candidate.suffix.lower() in {".py", ".ps1", ".sh"}:
            return candidate
    return None


def _synthetic_envelope(event: str, stem: str, scratch_root: Path) -> str:
    transcript_path: Path | None = None
    if stem in {"check-bugfix-discipline", "check-git-push-gate"}:
        transcript_path = scratch_root / f"{stem}.jsonl"
        user_text = (
            "the login page is broken, fix it"
            if stem == "check-bugfix-discipline"
            else "push these changes"
        )
        transcript_path.write_text(
            json.dumps(
                {
                    "type": "user",
                    "message": {
                        "role": "user",
                        "content": [{"type": "text", "text": user_text}],
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
    if event == "PreToolUse":
        payload = {
            "hookEventName": event,
            "tool_name": "Edit",
            "tool_input": {},
        }
        if stem == "check-git-push-gate":
            payload["tool_name"] = "Bash"
            payload["tool_input"] = {"command": "git push"}
        if transcript_path is not None:
            payload["transcript_path"] = str(transcript_path)
    elif event == "Stop":
        payload = {"hookEventName": event, "last_assistant_message": "done"}
    elif event == "SessionStart":
        payload = {"hookEventName": event, "source": "startup"}
    else:
        payload = {"hookEventName": event, "prompt": "health check"}
    return json.dumps(payload)


def verify_config(
    *,
    target: Path,
    platform: str,
    host_os: str,
    repo_root: Path,
    verify_fires: bool,
) -> list[str]:
    data = _load(target)
    expected = _manifest_stems(repo_root, platform)
    rows = list(_iter_owned_hooks(data, expected, platform, host_os))
    counts: dict[str, int] = {stem: 0 for stem in expected}
    messages: list[str] = []
    with tempfile.TemporaryDirectory(prefix="orchestrarium-hook-health-") as scratch:
        scratch_root = Path(scratch)
        foreign_cwd = scratch_root / "foreign-cwd"
        foreign_cwd.mkdir()
        for event, stem, argv in rows:
            counts[stem] += 1
            executable = _resolve_executable(argv[0], host_os)
            target_path = _target_path(argv)
            if target_path is not None:
                if not target_path.is_absolute():
                    raise ValueError(f"registered target is not absolute for {stem}: {target_path}")
                if not target_path.is_file():
                    raise ValueError(f"registered target is missing for {stem}: {target_path}")
            if verify_fires:
                completed = subprocess.run(
                    [str(executable), *argv[1:]],
                    input=_synthetic_envelope(event, stem, scratch_root),
                    capture_output=True,
                    text=True,
                    timeout=15,
                    cwd=foreign_cwd,
                )
                if completed.returncode != 0:
                    raise ValueError(
                        f"{stem} failed to fire (exit {completed.returncode}): "
                        f"{completed.stderr.strip()}"
                    )
                if stem in {"check-bugfix-discipline", "check-git-push-gate"}:
                    if '"permissionDecision"' not in completed.stdout or '"deny"' not in completed.stdout:
                        raise ValueError(
                            f"{stem} fired without its expected deny payload: "
                            f"{completed.stdout.strip()}"
                        )
            messages.append(f"PASS {platform} {event} {stem}")
    missing = sorted(stem for stem, count in counts.items() if count == 0)
    duplicates = sorted(stem for stem, count in counts.items() if count > 1)
    if missing:
        raise ValueError("missing registered hooks: " + ", ".join(missing))
    if duplicates:
        raise ValueError("duplicate registered hooks: " + ", ".join(duplicates))
    return messages


def _default_checks(repo_root: Path) -> list[tuple[Path, str, Path]]:
    home = Path.home()
    return [
        (home / ".claude" / "settings.json", "claude", home / ".claude" / "agents"),
        (home / ".codex" / "hooks.json", "codex", home / ".codex" / "skills" / "lead"),
    ]


def _leftover_wrappers(
    installed_root: Path,
    repo_root: Path,
    platform: str,
) -> list[Path]:
    stems = _manifest_stems(repo_root, platform)
    leftovers: list[Path] = []
    for subdir in ("scripts", "hooks"):
        for stem in sorted(stems):
            for extension in (".ps1", ".sh"):
                candidate = installed_root / subdir / f"{stem}{extension}"
                if candidate.is_file():
                    leftovers.append(candidate)
    return leftovers


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", help="Explicit settings.json or hooks.json")
    parser.add_argument("--platform", choices=("claude", "codex"))
    parser.add_argument("--host-os", choices=("posix", "windows"))
    parser.add_argument("--installed-root", help="Provider root containing scripts/ and hooks/")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--verify-fires", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).expanduser().resolve()
    host_os = args.host_os or ("windows" if os.name == "nt" else "posix")
    try:
        if args.target or args.platform:
            if not args.target or not args.platform:
                raise ValueError("--target and --platform must be supplied together")
            checks = [
                (
                    Path(args.target).expanduser(),
                    args.platform,
                    Path(args.installed_root).expanduser() if args.installed_root else None,
                )
            ]
        else:
            checks = _default_checks(repo_root)
        for target, platform, installed_root in checks:
            for message in verify_config(
                target=target,
                platform=platform,
                host_os=host_os,
                repo_root=repo_root,
                verify_fires=args.verify_fires,
            ):
                print(message)
            if installed_root is not None:
                for wrapper in _leftover_wrappers(installed_root, repo_root, platform):
                    print(f"WARN leftover hook wrapper: {wrapper}")
        return 0
    except (OSError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        sys.stderr.write(f"FAIL: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
