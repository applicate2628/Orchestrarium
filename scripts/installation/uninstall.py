"""Explicit-current removal using the existing transaction and receipt codec.

A preview token binds current objects, not historical physical ownership.
Unknown configuration and linked namespaces are never silently adopted.
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
    controls = codec.fresh_control_paths(provider, scope)
    paths = [receipt, *(anchor / p for p in record["files"]),
             *(anchor / p for p in controls)]
    apply = bool(args.apply and not args.dry_run)
    with backend._InstallTransaction(paths, enabled=apply) as transaction:
        owner = backend._CreateOnlyMutablePath(anchor, transaction, dry_run=not apply)
        if backend._read_owned_text(receipt, owner, preserve_newlines=True).encode("utf-8") != before:
            raise ValueError("E_UNINSTALL_RECEIPT_DRIFT")
        receipt_node = transaction._capture_node(receipt)
        observed, witnesses = {}, []
        for relative in sorted(set(record["files"]) | controls):
            path = owner.destination(Path(relative))
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
        control_remove, unresolved = [], []
        state = dict(witnesses)
        for relative in sorted(controls):
            current = state[relative]
            if current is None:
                continue
            claim = configs.get(relative)
            if (claim is not None and claim["kind"] in {"created-file", "file"}
                and current[0] == "file" and current[1] == claim["sha256"]):
                control_remove.append(relative)
            else:
                unresolved.append(relative)
        # Unknown or edited controls may still invoke the payload. Do not leave
        # registrations pointing to removed handlers, or erase user settings.
        remove = list(classified["remove"]) if not unresolved else []
        preserve = sorted(set(record["files"]) - set(classified["absent"]) - set(remove))
        token = hashlib.sha256(json.dumps(
            [hashlib.sha256(before).hexdigest(), receipt_node.python_identity,
             backend._CreateOnlyMutablePath._identity(anchor), witnesses],
            sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        print(json.dumps({"selection": token, "removeFiles": remove,
                          "removeControls": control_remove if not unresolved else [],
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
            return 2
        for relative in control_remove:
            owner.remove_exact_file(Path(relative), configs[relative]["sha256"])
        for relative in remove:
            owner.remove_exact_file(Path(relative), record["files"][relative])
        residual = dict(record)
        residual["files"] = {p: record["files"][p] for p in preserve}
        residual["configs"] = {p: v for p, v in configs.items()
                               if p not in control_remove and state.get(p) is not None}
        payload = codec.serialize_record(residual, provider, scope)
        owner.replace_file_atomic(receipt.relative_to(anchor), payload, fsync="required")
        if backend._read_owned_text(receipt, owner, preserve_newlines=True).encode("utf-8") != payload:
            raise ValueError("E_UNINSTALL_RECEIPT_READBACK")
        transaction.commit()
    print("RESULT: selected current content removed; unrecorded data retained")
    return 2 if preserve else 0
