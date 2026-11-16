"""Selected-provider uninstall through the existing installer transaction owner."""
from __future__ import annotations

import hashlib
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


def _run_owned_copies(backend, root: Path, provider: str, args) -> int:
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
    if record.get("layout") != codec.LAYOUT:
        raise ValueError("Ownership layout changed during uninstall")
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
        if provider == "codex" and scope == "global" and any(
            relative in backend.get_client(provider)["documents"]["global"]
            for relative, _before, _after in config_effects
        ):
            print("NOTICE: Removing global instructions can affect global-backed project "
                  "installations. Project files are not scanned or changed; reinstall "
                  "those projects with --standalone-instructions for independent use.")
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


def _run_selected_current(backend, root: Path, provider: str, args) -> int:
    mode, target, project = backend._target(provider, args)
    scope = "global" if mode == "global" else "project"
    anchor = backend._resolve_global_home() if project is None else project
    codec = backend._load_module_from_path("orche_uninstall_ownership", root / "scripts/installation/ownership.py")
    receipt = target / codec.RECEIPT_NAME
    if not anchor.is_dir():
        print("RESULT: no installation directory")
        return 0
    reader_tx = backend._InstallTransaction([receipt], enabled=False)
    reader = backend._CreateOnlyMutablePath(anchor, reader_tx, dry_run=True)
    reader.destination(receipt.relative_to(anchor))
    raw = backend._read_owned_text(receipt, reader, preserve_newlines=True)
    if raw is None:
        print("RESULT: no ownership receipt; all existing content preserved")
        return 0
    before = raw.encode("utf-8")
    record = codec.decode_record(before, provider, scope)
    if record.get("layout") is not None:
        raise ValueError("Ownership layout changed during uninstall")
    configuration = backend._load_module_from_path("orche_uninstall_configuration", root / "scripts/installation/configuration.py")
    controls = codec.fresh_control_paths(provider, scope)
    document_paths = codec.get_client(provider)["documents"][scope]
    bindings = {}
    for name in sorted(backend._CLAUDE_LINKED_SUBROOT_NAMES):
        logical = target / name
        if any((anchor / p).is_relative_to(logical) for p in record["files"]):
            resolved, authority = backend._resolve_global_claude_linked_subroot(
                root, target, mode, name)
            if authority is not None:
                bindings[logical] = (resolved, authority)
    def location(relative):
        logical = anchor / relative
        for prefix, (resolved, authority) in bindings.items():
            if logical.is_relative_to(prefix):
                return resolved / logical.relative_to(prefix), authority
        return logical, None
    paths = [receipt, *(location(p)[0] for p in record["files"]),
             *(anchor / p for p in controls)]
    if len(set(paths)) != len(paths):
        raise ValueError("E_UNINSTALL_DESTINATION_ALIAS")
    binding_witnesses = [
        (str(logical.relative_to(anchor)), authority.logical_identity,
         str(authority.resolved_root), authority.resolved_identity, authority.link_chain)
        for logical, (_, authority) in bindings.items()]
    apply = bool(args.apply and not args.dry_run)
    for _, authority in bindings.values():
        authority.assert_current()
    with backend._InstallTransaction(paths, enabled=apply) as transaction:
        owner = backend._CreateOnlyMutablePath(anchor, transaction, dry_run=not apply)
        if backend._read_owned_text(receipt, owner, preserve_newlines=True).encode("utf-8") != before:
            raise ValueError("E_UNINSTALL_RECEIPT_DRIFT")
        receipt_node = transaction._capture_node(receipt)
        linked_owners = {
            logical: backend._CreateOnlyMutablePath(resolved, transaction,
                dry_run=not apply, linked_authority=authority)
            for logical, (resolved, authority) in bindings.items()}
        def destination(relative):
            path, authority = location(relative)
            selected = owner if authority is None else linked_owners[authority.logical_root]
            return selected, path.relative_to(selected.anchor)
        observed, witnesses, documents = {}, [], {}
        configs = record.get("configs", {})
        for relative in sorted(set(record["files"]) | controls):
            selected, suffix = destination(relative)
            claim = configs.get(relative)
            if relative in document_paths:
                path = selected.destination(suffix, allow_leaf_reparse=True)
                binding = transaction._bind_scalar_storage(path)
                storage, node, chain, leaf = binding
                if node is not None:
                    documents[relative] = (binding, transaction._image_file_bytes(storage, node))
                witnesses.append((relative, None if node is None else
                                  (node.kind, node.data, node.python_identity)))
                continue
            path = selected.destination(suffix)
            try:
                node = transaction._capture_node(path)
            except FileNotFoundError:
                node = None
            witnesses.append((relative, None if node is None else
                              (node.kind, node.data, node.python_identity)))
            if relative in record["files"] and node is not None:
                observed[relative] = node.data if node.kind == "file" else None
        classified = codec.plan_file_removal(record, observed)
        configs = record.get("configs", {})
        control_remove, unresolved, block_updates, absent_blocks = [], [], {}, set()
        state = dict(witnesses)
        for relative in sorted(controls):
            current = state[relative]
            if current is None:
                continue
            claim = configs.get(relative)
            if (claim is not None and claim["kind"] in {"created-file", "file"}
                and current[0] == "file" and current[1] == claim["sha256"]):
                control_remove.append(relative)
            elif claim is not None and claim["kind"] == "block" and current[0] == "file":
                text = documents[relative][1].decode("utf-8")
                if hashlib.sha256(text.encode("utf-8")).hexdigest() != current[1]:
                    raise ValueError("E_UNINSTALL_DOCUMENT_DRIFT")
                try:
                    replacement = configuration.remove_owned_block(
                        text, claim["blockKind"], claim["sha256"],
                        backend._markdown_document_context)
                except ValueError:
                    unresolved.append(relative)
                else:
                    if replacement == text:
                        absent_blocks.add(relative)
                    else:
                        block_updates[relative] = replacement.encode("utf-8")
            else:
                unresolved.append(relative)
        # Unknown or edited controls may still invoke the payload. Do not leave
        # registrations pointing to removed handlers, or erase user settings.
        remove = list(classified["remove"]) if not unresolved else []
        preserve = sorted(set(record["files"]) - set(classified["absent"]) - set(remove))
        token = hashlib.sha256(json.dumps(
            [hashlib.sha256(before).hexdigest(), receipt_node.python_identity,
             backend._CreateOnlyMutablePath._identity(anchor), binding_witnesses, witnesses,
             [(key, str(bound[0][0]), str(bound[0][3]),
               [(str(path), node.kind, node.data, node.python_identity, repr(node.native_proof))
                for path, node in bound[0][2]])
              for key, bound in sorted(documents.items())]],
            sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        print(json.dumps({"selection": token, "removeFiles": remove,
                          "removeControls": control_remove if not unresolved else [],
                          "removeBlocks": sorted(block_updates) if not unresolved else [],
                          "preservedFiles": preserve, "unresolvedControls": unresolved},
                         sort_keys=True))
        if not apply:
            print("RESULT: preview only; review exact current selection before --apply")
            return 0
        if args.uninstall_selection != token:
            raise ValueError("E_UNINSTALL_SELECTION_DRIFT")
        if unresolved:
            transaction.commit()  # Settled no-op; all content is preserved.
            print("RESULT: preserved installation; control ownership is incomplete")
            return 2 if record["files"] or configs else 0
        current_documents = {key: value[0] for key, value in documents.items()}
        def assert_documents():
            for key, expected in current_documents.items():
                if transaction._bind_scalar_storage(anchor / key) != expected:
                    raise ValueError("E_UNINSTALL_DOCUMENT_DRIFT")
        assert_documents()
        for relative, replacement in block_updates.items():
            path = anchor / relative
            binding, original = documents[relative]
            def render(_path):
                if transaction._bind_scalar_storage(path) != binding:
                    raise ValueError("E_UNINSTALL_DOCUMENT_DRIFT")
                return replacement
            with transaction.direct_operation():
                transaction.transform_scalar(path, path, render, owner)
            after = transaction._bind_scalar_storage(path)
            if (after[0] != binding[0] or after[2:] != binding[2:]
                    or transaction._image_file_bytes(after[0], after[1]) != replacement):
                raise ValueError("E_UNINSTALL_DOCUMENT_READBACK")
            current_documents[relative] = after
        for relative in control_remove:
            owner.remove_exact_file(Path(relative), configs[relative]["sha256"])
        for relative in remove:
            selected, suffix = destination(relative)
            selected.remove_exact_file(suffix, record["files"][relative])
        for _, authority in bindings.values():
            authority.assert_current()
        assert_documents()
        residual = dict(record)
        residual["files"] = {p: record["files"][p] for p in preserve}
        residual["configs"] = {p: v for p, v in configs.items()
                               if p not in control_remove and p not in block_updates
                               and p not in absent_blocks and state.get(p) is not None}
        payload = codec.serialize_record(residual, provider, scope)
        owner.replace_file_atomic(receipt.relative_to(anchor), payload, fsync="required")
        if backend._read_owned_text(receipt, owner, preserve_newlines=True).encode("utf-8") != payload:
            raise ValueError("E_UNINSTALL_RECEIPT_READBACK")
        for _, authority in bindings.values():
            authority.assert_current()
        assert_documents()
        transaction.commit()
    print("RESULT: selected current content removed; unrecorded data retained")
    return 2 if preserve else 0


def run(backend, root: Path, provider: str, args) -> int:
    """Route by the existing receipt layout without granting migration authority."""
    mode, target, project = backend._target(provider, args)
    scope = "global" if mode == "global" else "project"
    anchor = backend._resolve_global_home() if project is None else project
    codec = backend._provider_ownership_module(root)
    receipt = target / codec.RECEIPT_NAME
    if not anchor.is_dir():
        print("RESULT: no selected installation directory")
        return 0
    reader_tx = backend._InstallTransaction([receipt], enabled=False)
    reader = backend._CreateOnlyMutablePath(anchor, reader_tx, dry_run=True)
    raw = backend._read_owned_text(receipt, reader, preserve_newlines=True)
    if raw is None:
        print("RESULT: no ownership record; existing files preserved")
        return 0
    record = codec.decode_record(raw.encode("utf-8"), provider, scope)
    if record.get("layout") == codec.LAYOUT:
        if getattr(args, "uninstall_selection", None) is not None:
            raise ValueError("Current-selection token does not authorize copy-layout uninstall")
        return _run_owned_copies(backend, root, provider, args)
    if provider != "claude":
        raise ValueError("Selected-current uninstall is qualified only for Claude")
    return _run_selected_current(backend, root, provider, args)
