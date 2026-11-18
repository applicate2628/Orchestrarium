"""Antigravity startup projection using the qualified installer transaction owner.

Discovery: https://antigravity.google/docs/customization-discovery/
Hook wire: https://antigravity.google/docs/hooks/
No provider process, account, tool approval or native lifecycle execution.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shlex
import sys


def run(backend, root: Path, args) -> int:
    if any(value for name, value in vars(args).items()
           if name.startswith(("replace_", "migrate_", "enroll_"))):
        raise ValueError("Selected maintenance option belongs to another client")
    mode, target, project = backend._target("antigravity", args)
    scope = "global" if mode == "global" else "project"
    anchor = backend._resolve_global_home() if project is None else project
    if not anchor.is_dir():
        raise ValueError("Selected project/home directory does not exist")
    codec = backend._provider_ownership_module(root)
    config = backend._provider_configuration_module(root)
    source = root / "adapters/antigravity"
    payloads = {target / name: (source / name).read_bytes() for name in (
        "runtime/session_start.py", "runtime/pre_tool_use.py", "runtime/command_advisory.py", "skills/orchestrarium-lead/SKILL.md",
        "rules/orchestrarium.md", "AGENTS.antigravity.md")}
    payloads[target / "AGENTS.shared.md"] = (root / "shared/AGENTS.shared.md").read_bytes()
    for relative in ("hooks/check-machine-local-path.py", "hooks/check-no-trash-in-repo.py",
                     "scripts/hook_common.py", "scripts/git_push_gate_preflight.py"):
        payloads[target / "runtime/shared" / relative] = (root / "scripts/universal-hooks" / relative).read_bytes()
    # The shared transport is an ordinary, independently owned copy, never a
    # lookup through another client's skills or global installation.
    for runtime_source, runtime_target in backend._runtime_file_destinations(root, target / "scripts"):
        payloads[runtime_target] = runtime_source.read_bytes()
    # Output safety uses the same adjacent classifier contract as other packs.
    for relative in ("hooks/check-machine-local-path.py", "scripts/hook_common.py"):
        payloads[target / relative] = (root / "scripts/universal-hooks" / relative).read_bytes()
    base = target.parent
    discovery_base = target.relative_to(anchor).as_posix() if project is not None else target.name
    argv = [sys.executable, str(target / "runtime/session_start.py")]
    command = backend._hook_health_module(root).serialize_windows_hook_command(argv) if os.name == "nt" else shlex.join(argv)
    tool_argv = [sys.executable, str(target / "runtime/pre_tool_use.py")]
    tool_command = backend._hook_health_module(root).serialize_windows_hook_command(tool_argv) if os.name == "nt" else shlex.join(tool_argv)
    audit_argv = [sys.executable, str(target / "runtime/command_advisory.py")]
    audit_command = backend._hook_health_module(root).serialize_windows_hook_command(audit_argv) if os.name == "nt" else shlex.join(audit_argv)
    specs = {
        base / "hooks.json": {"kind": "json-projection", "members": {
            "orchestrarium-session-start": {"SessionStart": [{"type": "command", "command": command}]},
            "orchestrarium-machine-local-path": {"PreToolUse": [{"matcher": "^(write_to_file|replace_file_content)$",
                "hooks": [{"type": "command", "command": tool_command}]}]},
            "orchestrarium-stray-artifact": {"PreToolUse": [{"matcher": "^run_command$",
                "hooks": [{"type": "command", "command": audit_command}]}]}}, "entries": []},
        base / "skills.json": {"kind": "json-projection", "members": {}, "entries": [{"path": discovery_base + "/skills"}]},
        base / "rules.json": {"kind": "json-projection", "members": {}, "entries": [{"path": discovery_base + "/rules"}]},
    }
    if args.no_hypothesis_hook or os.environ.get("ORCHESTRARIUM_NO_HYPOTHESIS_HOOK"):
        specs.pop(base / "hooks.json")
    receipt = target / codec.RECEIPT_NAME
    paths = [target, *specs]
    # The common owner retains all prior bytes and rolls back failed publications.
    with backend._InstallTransaction(paths, enabled=not args.dry_run) as transaction:
        owner = backend._CreateOnlyMutablePath(anchor, transaction, dry_run=args.dry_run)
        text = backend._read_owned_text(receipt, owner, preserve_newlines=True)
        receipt_before = None if text is None else text.encode("utf-8")
        prior = None if receipt_before is None else codec.decode_record(receipt_before, "antigravity", scope)
        previous_files = {} if prior is None else prior["files"]
        previous_configs = {} if prior is None else prior.get("configs", {})
        planned = {}
        for path, payload in payloads.items():
            relative = path.relative_to(anchor).as_posix()
            current = backend._read_owned_text(path, owner, preserve_newlines=True)
            old = None if current is None else current.encode("utf-8")
            if old is not None and previous_files.get(relative) != hashlib.sha256(old).hexdigest():
                raise ValueError("Unowned or modified Antigravity payload preserved")
            planned[path] = (old, payload)
        config_records = {}
        # A previously installed hook remains owned when hook installation is disabled.
        for relative, spec in previous_configs.items():
            if anchor / relative not in specs:
                config_records[relative] = spec
        for path, spec in specs.items():
            relative = path.relative_to(anchor).as_posix()
            text = backend._read_owned_text(path, owner, preserve_newlines=True)
            old = None if text is None else text.encode("utf-8")
            planned[path] = (old, config.json_projection(old, previous_configs.get(relative), spec))
            config_records[relative] = spec
        file_records = dict(previous_files)
        file_records.update({path.relative_to(anchor).as_posix(): hashlib.sha256(data).hexdigest()
                             for path, data in payloads.items()})
        receipt_bytes = codec.encode_record(file_records, "antigravity", scope, configs=config_records)
        planned[receipt] = (receipt_before, receipt_bytes)
        if not args.dry_run:
            for path, (old, payload) in planned.items():
                relative = path.relative_to(anchor)
                if old is None:
                    owner.create_file(relative, payload)
                elif old != payload:
                    owner.replace_exact_file(relative, hashlib.sha256(old).hexdigest(), payload)
                if backend._read_owned_text(path, owner, preserve_newlines=True).encode("utf-8") != payload:
                    raise ValueError("Antigravity projection readback failed")
            transaction.commit()
    print("RESULT: " + ("preview only" if args.dry_run else "Antigravity startup projection installed") + "; no native agent launched")
    return 0
