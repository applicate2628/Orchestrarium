"""Selected-provider uninstall through the existing installer transaction owner."""
from __future__ import annotations

import json
import os
from pathlib import Path


def _remove_hooks(backend, root, data, spec, provider, scope, anchor, codec):
    helper = backend._load_module_from_path("orche_uninstall_hook_writer", root / "scripts/install-hypothesis-hook.py")
    health = backend._hook_health_module(root)
    host = "windows" if os.name == "nt" else "posix"
    targets = {}
    for record in spec["handlers"]:
        argv = health._command_argv(record["handler"], provider, host)
        script, _ = health._invoked_script(argv)
        if script is None:
            raise ValueError("Owned hook has no script target")
        codec.validate_path(Path(script).relative_to(anchor).as_posix(), provider,
                            scope)
        targets.setdefault(record["marker"], set()).add(script)
    candidate = dict(data)
    candidate.setdefault("hooks", {})
    for event, _gi, _hi, group, handler, invocation in health._owned_records(
        candidate, set(targets), provider, host, targets):
        context = {key: value for key, value in group.items() if key != "hooks"}
        if not any(record["event"] == event and record["marker"] == invocation.marker
                   and record["context"] == context and record["handler"] == handler
                   for record in spec["handlers"]):
            raise ValueError("Modified owned hook preserved")
    for record in spec["handlers"]:
        helper.remove(data, record["event"], record["marker"],
                      expected_entry={**record["context"], "hooks": [record["handler"]]},
                      platform=provider, host_os=host, managed_targets=targets)
    candidate = dict(data)
    candidate.setdefault("hooks", {})
    if list(health._owned_records(candidate, set(targets), provider, host, targets)):
        raise ValueError("Owned hook removal did not settle")
    agent_key = codec.get_client(provider)["default_agent_key"]
    if spec["agentAdded"] and agent_key is not None and data.get(agent_key) == "lead":
        del data[agent_key]
    return helper.encode_hook_config(data)


def run(backend, root: Path, provider: str, args) -> int:
    mode, target, project = backend._target(provider, args)
    backend._require_provider_copy_isolation(root, provider, mode, target, project, removing=True)
    scope = "global" if mode == "global" else "project"
    anchor = backend._resolve_global_home() if project is None else project
    codec = backend._provider_ownership_module(root)
    configuration = backend._provider_configuration_module(root)
    receipt_path = target / codec.RECEIPT_NAME
    if not anchor.is_dir():
        print("RESULT: no selected installation directory")
        return 0
    reader_tx = backend._InstallTransaction([receipt_path], enabled=False)
    reader = backend._CreateOnlyMutablePath(anchor, reader_tx, dry_run=True)
    reader.destination(receipt_path.relative_to(anchor))
    if not receipt_path.exists():
        print("RESULT: no ownership record; existing files preserved")
        return 0
    if receipt_path.stat().st_size > codec.MAX_BYTES:
        raise ValueError("Ownership record exceeds limit")
    before = receipt_path.read_bytes()
    record = codec.decode_record(before, provider, scope)
    if "configs" not in record:
        raise ValueError("Legacy receipt lacks configuration ownership; migration required")
    apply = bool(args.apply and not args.dry_run)
    paths = [receipt_path, *(anchor / path for path in record["files"]),
             *(anchor / path for path in record["configs"]),
             *(anchor / path for path in record.get("directories", []))]
    # One snapshot per enclosing root, not one repeated tree snapshot per member.
    minimal_paths = []
    for path in sorted(set(paths), key=lambda value: len(value.parts)):
        if not any(base == path or base in path.parents for base in minimal_paths):
            minimal_paths.append(path)
    with backend._InstallTransaction(minimal_paths, enabled=apply) as transaction:
        owner = backend._CreateOnlyMutablePath(anchor, transaction, dry_run=not apply)
        if backend._read_owned_text(receipt_path, owner).encode("utf-8") != before:
            raise ValueError("Ownership record changed during uninstall")
        observed = {}
        for relative in record["files"]:
            path = owner.destination(Path(relative), allow_leaf_reparse=True)
            try:
                node = transaction._capture_node(path)
            except FileNotFoundError:
                continue
            except OSError:
                observed[relative] = None
            else:
                observed[relative] = node.data if node.kind == "file" else None
        plan = codec.plan_file_removal(record, observed)
        preserve = set(plan["preserve"])
        protected_skills = {"/".join(path.split("/")[:3]) + "/" for path in preserve
                            if len(path.split("/")) > 3 and path.split("/")[1] == "skills"}
        remove = [path for path in plan["remove"] if not any(path.startswith(prefix) for prefix in protected_skills)]
        preserve.update(set(plan["remove"]) - set(remove))
        config_effects = []
        residual_configs = {}
        for relative, spec in record["configs"].items():
            path = owner.destination(Path(relative))
            text = backend._read_owned_text(path, owner)
            if text is None:
                continue
            payload = text.encode("utf-8")
            if spec["kind"] == "block":
                after = configuration.remove_owned_block(text, spec["blockKind"], spec["sha256"], backend._claude_document_context).encode("utf-8")
            elif spec["kind"] == "native-roles":
                after = configuration.remove_native_roles(payload, spec["roles"])
                after = configuration.remove_native_features(after, spec.get("features", {}))
            elif spec["kind"] == "hooks":
                after = _remove_hooks(backend, root, json.loads(text), spec, provider, scope, anchor, codec)
            else:
                if backend.hashlib.sha256(payload).hexdigest() != spec["sha256"]:
                    residual_configs[relative] = spec
                    continue
                after = None
            if after != payload:
                config_effects.append((relative, payload, after))
        print(json.dumps({"provider": provider, "apply": apply, "removeFiles": len(remove),
                          "preservedFiles": sorted(preserve), "absentFiles": len(plan["absent"]),
                          "configurationChanges": len(config_effects),
                          "preservedConfiguration": sorted(residual_configs),
                          "runtime": "retained; interpreter lifecycle is separate"}, sort_keys=True))
        if not apply:
            print("RESULT: uninstall preview only; pass --apply to remove owned content")
            return 0
        # Deactivate registrations/instructions before removing their runtime payload.
        for relative, payload, after in config_effects:
            path = anchor / relative
            if backend._read_owned_text(path, owner).encode("utf-8") != payload:
                raise ValueError("Configuration changed during uninstall")
            if after is None:
                owner.remove_exact_file(Path(relative), backend.hashlib.sha256(payload).hexdigest())
            else:
                owner.replace_file_atomic(Path(relative), after, fsync="required")
        # Retain maximal wholly-owned trees before individual file tombstones
        # are created. Otherwise those rollback artifacts make every containing
        # directory appear nonempty until commit, leaving empty install trees.
        owned_directories = set(record.get("directories", []))
        removable_files = set(remove)
        removed_roots = []
        for relative in sorted(owned_directories, key=lambda value: (len(Path(value).parts), value)):
            path = anchor / relative
            if any(base == path or base in path.parents for base in removed_roots):
                continue
            owner.destination(Path(relative), allow_leaf_reparse=True)
            image = transaction._observe(path)
            if not image or image[path].kind != "directory":
                continue
            eligible = True
            for member, node in image.items():
                name = member.relative_to(anchor).as_posix()
                if node.kind == "directory":
                    eligible = name in owned_directories
                else:
                    eligible = (node.kind == "file" and name in removable_files
                                and node.data == record["files"].get(name))
                if not eligible:
                    break
            if eligible:
                owner.retain_path(Path(relative), image)
                removed_roots.append(path)
        for relative in remove:
            path = anchor / relative
            if not any(base in path.parents for base in removed_roots):
                owner.remove_exact_file(Path(relative), record["files"][relative])
        remaining_directories = []
        for relative in sorted(record.get("directories", []), key=lambda value: (-len(Path(value).parts), value)):
            path = owner.destination(Path(relative), allow_leaf_reparse=True)
            image = transaction._observe(path)
            if not image:
                continue
            if len(image) == 1 and image[path].kind == "directory":
                owner.retain_path(Path(relative), image)
            else:
                remaining_directories.append(relative)
        remaining = {path: record["files"][path] for path in sorted(preserve)}
        payload = codec.encode_record(remaining, provider, scope, configs=residual_configs, directories=sorted(remaining_directories))
        owner.replace_file_atomic(receipt_path.relative_to(anchor), payload, fsync="required")
        if backend._read_owned_text(receipt_path, owner).encode("utf-8") != payload:
            raise ValueError("Uninstall record readback failed")
        transaction.commit()
    if preserve or residual_configs:
        print("RESULT: partial uninstall; modified content preserved")
        return 2
    print("RESULT: selected owned content removed; user files and runtime preserved")
    return 0
