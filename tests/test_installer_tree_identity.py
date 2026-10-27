"""Tree identity keeps structural boundaries and native rollback ownership."""
import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import production_installer as installer


def test_tree_identity_separates_legacy_stream_twins(tmp_path: Path) -> None:
    stock, twin = tmp_path / "stock", tmp_path / "twin"
    stock.mkdir()
    twin.mkdir()
    (stock / "a").write_bytes(b"body")
    (stock / "b").write_bytes(b"companion")
    (twin / "a").write_bytes(b"bodyF\0b\0companion")
    assert installer._legacy_tree_sha256(stock) == installer._legacy_tree_sha256(twin)
    assert installer._tree_sha256(stock) != installer._tree_sha256(twin)


def test_tree_identity_keeps_descriptor_backed_file_reads(tmp_path: Path, monkeypatch) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "empty").write_bytes(b"")
    (tree / "nested").mkdir()
    transaction = installer._InstallTransaction([], enabled=False)
    image = transaction._observe(tree)
    expected = installer._tree_sha256(tree)
    reads = []

    def read(path):
        reads.append(path.relative_to(tree).as_posix())
        return transaction._image_file_bytes(path, image[path])

    def forbidden_path_read(_path):
        raise AssertionError("tree identity reopened a descriptor-backed file")

    monkeypatch.setattr(Path, "read_bytes", forbidden_path_read)
    assert transaction._image_tree_digest(tree, image, read_file=read) == expected
    assert reads == ["empty"]


@pytest.mark.parametrize("watched", (False, True))
def test_empty_file_and_nested_created_directory_rollback(tmp_path: Path, watched: bool) -> None:
    missing = tmp_path / "missing"
    transaction = installer._InstallTransaction([missing] if watched else [], enabled=True)
    primary = RuntimeError("tree-v2 nested rollback")
    with pytest.raises(RuntimeError) as caught:
        with transaction:
            owner = installer._CreateOnlyMutablePath(tmp_path, transaction, dry_run=False)
            leaf = owner.create_file(Path("missing/nested/empty"), b"")
            assert installer._file_sha256(leaf) == hashlib.sha256(b"").hexdigest()
            directory_records = [r for r in transaction._slice_a_created if r.kind == "directory"]
            assert len(directory_records) == 2
            assert all(r.digest == installer._tree_manifest_sha256(()) for r in directory_records)
            raise primary
    assert caught.value is primary
    assert not missing.exists()


@pytest.mark.parametrize("drift", ("foreign-child", "reparse"))
def test_created_directory_retirement_preserves_foreign_entry(tmp_path: Path, drift: str) -> None:
    transaction = installer._InstallTransaction([], enabled=False)
    owner = installer._CreateOnlyMutablePath(tmp_path, transaction, dry_run=False)
    born = tmp_path / "born"
    owner._ensure_directory_path(born)
    record = next(r for r in transaction._slice_a_created if r.leaf_path == born)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel"
    sentinel.write_bytes(b"foreign remains")
    if drift == "foreign-child":
        (born / "foreign").write_bytes(b"foreign child remains")
    else:
        born.rename(tmp_path / "original-born")
        born.symlink_to(outside, target_is_directory=True)
    before = transaction._observe(born)
    with pytest.raises(RuntimeError, match="E_ROLLBACK_CREATED_IDENTITY_CHANGED"):
        owner.rollback_created(record)
    assert transaction._observe(born) == before
    assert sentinel.read_bytes() == b"foreign remains"


@pytest.mark.parametrize("schema", (installer._LEAD_RECEIPT_SCHEMA, installer._LEAD_LEGACY_RECEIPT_SCHEMA))
def test_lead_receipt_retains_identity_algorithm(tmp_path: Path, schema: str) -> None:
    path = tmp_path / "receipt"
    digest = installer._tree_manifest_sha256(())
    payload = installer._lead_receipt_bytes(digest, schema=schema)
    path.write_bytes(payload)
    observed = installer._read_lead_receipt(path)
    assert observed[0] == payload
    assert observed[2:] == (digest, schema)


@pytest.mark.parametrize("kind", ("lead", "members"))
@pytest.mark.parametrize("evidence", ("strong", "legacy", "mismatch"))
def test_independent_structural_receipt_precedes_stock_fallback(
    tmp_path: Path, monkeypatch, kind: str, evidence: str,
) -> None:
    from test_global_nonlead_receipt import _apply, _fixture, NAMES, ROOT

    owner, source, home, skills, receipt_path = _fixture(tmp_path)
    _apply(owner, source, home, skills)
    baseline = owner._preflight_canonical_skills(source, skills, root=ROOT, global_install=True)
    try:
        with owner._InstallTransaction([skills], enabled=True) as transaction:
            publisher = owner._CreateOnlyMutablePath(home, transaction, dry_run=False)
            owner._finalize_canonical_lead_receipt(baseline, skills, publisher)
            transaction.commit()
    finally:
        owner._discard_canonical_skills_plan(baseline)
    assert owner._read_lead_receipt(skills / owner._LEAD_RECEIPT_NAME)[3] == owner._LEAD_RECEIPT_SCHEMA
    selected = ("lead",) if kind == "lead" else NAMES
    legacy = {name: owner._legacy_tree_sha256(skills / name, ignore_runtime_cache=True)
              for name in selected}
    # A real owned Version A publication supplies receipt/member evidence;
    # source Version B changes independently of the retained target.
    for name in selected:
        path = source / name / "SKILL.md"
        path.write_bytes(path.read_bytes() + b"\nVersion B source\n")
    if kind == "lead":
        if evidence != "strong":
            (skills / owner._LEAD_RECEIPT_NAME).write_bytes(owner._lead_receipt_bytes(
                legacy["lead"] if evidence == "legacy" else "0" * 64,
                schema=owner._LEAD_LEGACY_RECEIPT_SCHEMA if evidence == "legacy"
                else owner._LEAD_RECEIPT_SCHEMA,
            ))
        monkeypatch.setattr(owner, "GLOBAL_LEAD_ACCEPTED_PRIOR_TREE_SHA256", {
            legacy["lead"]: owner._tree_sha256(skills / "lead", ignore_runtime_cache=True)
            if evidence == "mismatch" else None,
        })
    else:
        if evidence != "strong":
            values = {}
            for name in selected:
                members = dict(owner._stage_tree_manifest(skills / name, ignore_runtime_cache=True))
                if evidence == "mismatch":
                    members["SKILL.md"] = "0" * 64
                values[name] = legacy[name] if evidence == "legacy" else {"members": members}
            receipt_path.write_bytes(owner._nonlead_receipt_bytes(
                values, schema=owner._NONLEAD_MEMBER_RECEIPT_SCHEMA,
            ))
        monkeypatch.setattr(owner, "ADDITIONAL_STOCK_SKILL_ACCEPTED_PRIOR_TREE_SHA256", {
            name: {legacy[name]: owner._tree_sha256(skills / name, ignore_runtime_cache=True)
                   if evidence == "mismatch" else None} for name in selected
        })
    before = owner._InstallTransaction._observe(skills)
    actual = owner._legacy_factory_identity_v2
    calls = []

    def stock(name, *args, **kwargs):
        if name in selected:
            calls.append(name)
            assert evidence == "legacy", "strong receiver touched optional stock fallback"
        return actual(name, *args, **kwargs)

    monkeypatch.setattr(owner, "_legacy_factory_identity_v2", stock)
    plan = None
    try:
        if evidence == "strong":
            plan = owner._preflight_canonical_skills(source, skills, root=ROOT, global_install=True)
        else:
            error = "E_LEGACY_TREE_WITNESS_UNAVAILABLE" if evidence == "legacy" else "RECEIPT_DRIFT"
            with pytest.raises(ValueError, match=error):
                plan = owner._preflight_canonical_skills(source, skills, root=ROOT, global_install=True)
    finally:
        if plan is not None:
            owner._discard_canonical_skills_plan(plan)
    assert owner._InstallTransaction._observe(skills) == before
    assert bool(calls) == (evidence == "legacy")
