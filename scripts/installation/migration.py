"""Lossless, selected-client legacy link conversion; no install or adoption.

Conversion is an explicit transaction before normal installation. It preserves
all copied user data and never grants uninstall ownership over unreceipted files.
"""

import stat
import hashlib


def _is_link(path):
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def plan(backend, anchor, provider):
    result = []
    for logical, dependency in backend.get_client(provider)["legacy_shared_roots"]:
        target = anchor / logical
        shared = anchor / dependency
        # Do not follow a linked parent/root in discovery or extend the selected
        # provider's write authority into another filesystem tree.
        if backend._contains_reparse(target.parent):
            raise ValueError("E_PROVIDER_PROJECTION_MIGRATION_COLLISION: linked parent")
        candidates = [target]
        if target.is_dir() and not _is_link(target):
            candidates = sorted(target.iterdir())
        for candidate in candidates:
            if not _is_link(candidate):
                continue
            source = candidate.resolve(strict=True)
            if (backend._contains_reparse(shared) or not shared.is_dir()
                or not source.is_dir()
                or not (source == shared or source.parent == shared)):
                raise ValueError("E_PROVIDER_PROJECTION_MIGRATION_COLLISION: unexpected referent")
            if any(_is_link(member) for member in source.rglob("*")):
                raise ValueError("E_PROVIDER_PROJECTION_MIGRATION_COLLISION: nested link")
            digest = backend._tree_sha256(source, ignore_runtime_cache=True)
            if digest is None:
                raise ValueError("E_PROVIDER_PROJECTION_MIGRATION_COLLISION: invalid source tree")
            result.append((candidate, source, digest))
    return result



def receipt_plan(backend, anchor, provider, entries):
    """Carry only the old receipts whose same-named skill links were converted."""
    skills = (anchor / backend.get_client(provider)["canonical_runtime"]).parent
    sources = {anchor / source for _target, source in backend.get_client(provider)["legacy_shared_roots"]}
    converted = {target.name: source for target, source, _digest in entries
                 if target.parent == skills and source.parent in sources
                 and target.name == source.name and source.parent != skills}
    if not converted:
        return []  # Whole-root copies already carry receipts; retired aliases own no new copy.
    parents = {source.parent for source in converted.values()}
    if len(parents) != 1:
        raise ValueError("E_PROVIDER_PROJECTION_MIGRATION_COLLISION: mixed receipt owners")
    source_root = next(iter(parents))
    receipts = []
    if "lead" in converted:
        source = source_root / backend._LEAD_RECEIPT_NAME
        prior = backend._read_lead_receipt(source)
        if prior is not None:
            if backend._lead_receipt_identity_v2(prior, converted["lead"]) != backend._tree_sha256(converted["lead"], ignore_runtime_cache=True):
                raise ValueError("E_CANONICAL_LEAD_RECEIPT_DRIFT")
            receipts.append((source, skills / source.name, prior[0], prior[0]))
    source = source_root / backend._NONLEAD_RECEIPT_NAME
    prior = backend._read_nonlead_receipt(source)
    if prior is not None:
        selected = {}
        for name, value in prior.entries:
            if name not in converted:
                continue
            if isinstance(value, str):
                # Legacy receipts identify a whole authenticated factory tree,
                # not a member manifest. Qualification returns its strong hash.
                backend._qualify_legacy_tree(name, converted[name], value)
            else:
                observed = dict(backend._stage_tree_manifest(converted[name], ignore_runtime_cache=True))
                if any(observed.get(path) != digest for path, digest in value):
                    raise ValueError("E_CANONICAL_SKILLS_RECEIPT_DRIFT")
            selected[name] = value if isinstance(value, str) else {"members": dict(value)}
        if selected:
            payload = backend._nonlead_receipt_bytes(selected, schema=prior.schema)
            receipts.append((source, skills / source.name, prior.payload, payload))
    for _source, target, _before, payload in receipts:
        if _is_link(target) or target.exists() and (not target.is_file() or target.read_bytes() != payload):
            raise ValueError("E_PROVIDER_PROJECTION_MIGRATION_COLLISION: existing receipt")
    return receipts


def run(backend, root, provider, args):
    mode, target, project = backend._target(provider, args)
    anchor = target.parent if mode == "global" else project
    entries = plan(backend, anchor, provider)
    receipts = receipt_plan(backend, anchor, provider, entries)
    apply = bool(args.apply and not args.dry_run)
    if not entries:
        print("RESULT: no selected legacy skill links; nothing changed")
        return 0
    links = tuple(target for target, source, digest in entries)
    sources = tuple(dict.fromkeys([*(source for target, source, digest in entries),
                                   *(source for source, _target, _before, _payload in receipts)]))
    with backend._InstallTransaction(
        [*sources, *links, *(target for _source, target, _before, _payload in receipts)], enabled=apply, link_object_paths=links,
        readonly_paths=sources,
    ) as transaction:
        owner = backend._CreateOnlyMutablePath(anchor, transaction, dry_run=not apply)
        for target, source, digest in entries:
            payloads = tuple(anchor / path for path in backend.get_client(provider)["payload_roots"])
            already_owned = any(source == path or path in source.parents for path in payloads)
            if already_owned:
                # This client already owns the ordinary source. Retire only the
                # obsolete alias, rather than creating a second installed copy.
                dependency = transaction.bind_readonly_path(owner, source)
                original = backend._admitted_mutation_image(transaction, target)
                if (len(original) != 1 or target not in original
                    or original[target].kind not in {"link", "reparse"}
                    or not backend._projection_resolves_to(target, source)
                    or transaction.readonly_tree_digest(dependency, ignore_runtime_cache=True) != digest):
                    raise ValueError("E_PROVIDER_PROJECTION_MIGRATION_DRIFT")
                owner.retain_path(target.relative_to(anchor), original,
                                  readonly_dependencies=(dependency,))
                action = "RETIRED ALIAS: "
            else:
                owner.materialize_exact_projection(target.relative_to(anchor), source, digest)
                action = "MATERIALIZED: "
            print((action if apply else "PREVIEW " + action)
                  + target.relative_to(anchor).as_posix())
        for source, target, before, payload in receipts:
            dependency = transaction.bind_readonly_path(owner, source)
            image = dict(dependency.image)
            if source not in image or image[source].kind != "file" or image[source].data != hashlib.sha256(before).hexdigest():
                raise ValueError("E_PROVIDER_PROJECTION_MIGRATION_DRIFT: receipt source")
            transaction.assert_readonly_path(dependency, check_content=True)
            owner.create_file(target.relative_to(anchor), payload)
            transaction.assert_readonly_path(dependency, check_content=True)
        if apply:
            transaction.commit()
    print("RESULT: selected copies settled; source data and other clients preserved"
          if apply else "RESULT: preview only; use --apply to convert these links")
    return 0
