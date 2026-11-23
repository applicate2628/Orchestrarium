"""Explicit-current removal using the existing transaction and receipt codec.

A preview token binds current objects, not historical physical ownership.
Unknown configuration is never silently adopted. Linked runtime subroots use
the existing global authority, bound to the explicit current preview.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

def run(backend, root: Path, provider: str, args) -> int:
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
        # Absence is also a selected state, retained through receipt publication.
        observed, witnesses, documents, current_controls = {}, [], {}, {}
        configs = record.get("configs", {})
        for relative in sorted(set(record["files"]) | controls):
            selected, suffix = destination(relative)
            claim = configs.get(relative)
            if relative in document_paths:
                path = selected.destination(suffix, allow_leaf_reparse=True)
                binding = transaction._bind_scalar_storage(path)
                storage, node, chain, leaf = binding
                documents[relative] = (
                    binding, None if node is None else transaction._image_file_bytes(storage, node))
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
            if relative in controls:
                current_controls[relative] = node
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
        def assert_control_state():
            for key, expected in current_documents.items():
                if transaction._bind_scalar_storage(anchor / key) != expected:
                    raise ValueError("E_UNINSTALL_DOCUMENT_DRIFT")
            for key, expected in current_controls.items():
                path = owner.destination(Path(key))
                image = {} if expected is None else {path: expected}
                if not transaction._image_matches(path, image):
                    raise ValueError("E_UNINSTALL_CONTROL_DRIFT")
        assert_control_state()
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
            if relative in current_documents:
                # Expect absence at the same storage, with the same traversal witnesses.
                storage, _, chain, leaf = current_documents[relative]
                current_documents[relative] = (storage, None, chain, leaf)
            if relative in current_controls:
                current_controls[relative] = None
        for relative in remove:
            selected, suffix = destination(relative)
            selected.remove_exact_file(suffix, record["files"][relative])
        for _, authority in bindings.values():
            authority.assert_current()
        assert_control_state()
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
        assert_control_state()
        transaction.commit()
    print("RESULT: selected current content removed; unrecorded data retained")
    return 2 if preserve else 0
