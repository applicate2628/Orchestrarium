"""Finalized target commitment is derived from the admitted source manifest."""
from dataclasses import replace
import hashlib
from pathlib import Path
import shutil

import pytest
from tests.test_hook_runtime_transactions import production_installer as installer


def fixture(tmp_path):
    home = tmp_path / "home"
    skills = home / ".agents/skills"
    source = tmp_path / "stage"
    source.mkdir()
    (source / "SKILL.md").write_bytes(b"synthetic canonical lead\n")
    (source / "retired.py").write_bytes(b"synthetic retired hook\n")
    lead = skills / "lead"
    shutil.copytree(source, lead)
    stage = installer._CanonicalLeadStage(source, installer._stage_tree_manifest(source),
                                          installer._tree_sha256(source))
    skill = installer._CanonicalSkillPlan("lead", source, stage.digest, stage.digest, None, True)
    plan = installer._CanonicalSkillsPlan(stage, (skill,), None)
    transaction = installer._InstallTransaction([], enabled=False)
    owner = installer._CreateOnlyMutablePath(home, transaction, dry_run=False)
    item = installer._SkillProjectionPlan("lead", lead, stage.digest, "create", None)
    retired = lead / "retired.py"
    removed = (retired, hashlib.sha256(retired.read_bytes()).hexdigest())
    return home, skills, source, lead, plan, owner, item, removed


@pytest.mark.parametrize("receipt", ("none", "new", "already-current"))
def test_finalizer_returns_source_derived_digest_on_every_success(tmp_path, monkeypatch, receipt):
    _, skills, _, lead, plan, owner, _, removed = fixture(tmp_path)
    removed[0].unlink()
    manifest = tuple(row for row in plan.stage.manifest if row[0] != "retired.py")
    expected = installer._tree_manifest_sha256(manifest)
    receipt_path = skills / installer._LEAD_RECEIPT_NAME
    if receipt != "none":
        if receipt == "already-current":
            receipt_path.write_bytes(installer._lead_receipt_bytes(expected))
        plan = replace(plan, lead_receipt=installer._LeadReceiptPlan(
            installer._read_lead_receipt(receipt_path), plan.stage.digest, plan.stage.path))
    def no_target_election(*_args, **_kwargs):
        raise AssertionError("finalizer must derive from the admitted manifest")
    monkeypatch.setattr(installer, "_tree_sha256", no_target_election)
    identity = receipt_path.stat().st_ino if receipt_path.exists() else None
    assert installer._finalize_canonical_lead_receipt(plan, skills, owner, (removed,)) == expected
    if receipt != "none":
        assert receipt_path.read_bytes() == installer._lead_receipt_bytes(expected)
    if identity is not None:
        assert receipt_path.stat().st_ino == identity


def test_no_removal_and_dry_run_keep_original_commitment_contract(tmp_path):
    _, skills, _, _, plan, owner, _, _ = fixture(tmp_path)
    assert installer._finalize_canonical_lead_receipt(plan, skills, owner) == plan.stage.digest
    owner.dry_run = True
    assert installer._finalize_canonical_lead_receipt(plan, skills, owner) is None
    assert not (skills / installer._LEAD_RECEIPT_NAME).exists()


@pytest.mark.parametrize("bad", ("unbound", "wrong-hash", "duplicate", "directory", "foreign-target"))
def test_finalizer_refuses_unqualified_projection_of_source(tmp_path, bad):
    _, skills, source, lead, plan, owner, _, removed = fixture(tmp_path)
    claims = (removed,)
    removed[0].unlink()
    if bad == "unbound":
        claims = ((lead / "unselected", removed[1]),)
    elif bad == "wrong-hash":
        claims = ((removed[0], "0" * 64),)
    elif bad == "duplicate":
        claims = (removed, removed)
    elif bad == "directory":
        (source / "empty").mkdir()
        stage = replace(plan.stage, manifest=installer._stage_tree_manifest(source),
                        digest=installer._tree_sha256(source))
        plan = replace(plan, stage=stage)
        claims = (removed, (lead / "empty", "directory"))
    else:
        (lead / "foreign").write_bytes(b"preserve foreign bytes")
    with pytest.raises(ValueError, match="E_MUTABLE_PATH_POSTCONDITION"):
        installer._finalize_canonical_lead_receipt(plan, skills, owner, claims)
    assert not (skills / installer._LEAD_RECEIPT_NAME).exists()
    if bad == "foreign-target":
        assert (lead / "foreign").read_bytes() == b"preserve foreign bytes"


@pytest.mark.parametrize("drift", (None, "source", "target"))
def test_compatibility_checks_original_source_and_final_target_independently(tmp_path, drift):
    _, skills, source, lead, plan, owner, item, removed = fixture(tmp_path)
    removed[0].unlink()
    finalized = installer._finalize_canonical_lead_receipt(plan, skills, owner, (removed,))
    assert finalized != item.canonical_digest == plan.stage.digest
    if drift:
        ((source if drift == "source" else lead) / "foreign").write_bytes(b"unapproved")
        with pytest.raises(ValueError, match="E_LEGACY_CODEX_SKILL_COLLISION:lead"):
            installer._assert_codex_legacy_canonical_current(
                (item,), plan, dry_run=False, finalized_lead_digest=finalized)
    else:
        installer._assert_codex_legacy_canonical_current(
            (item,), plan, dry_run=False, finalized_lead_digest=finalized)
        with pytest.raises(ValueError, match="E_LEGACY_CODEX_SKILL_COLLISION:lead"):
            installer._assert_codex_legacy_canonical_current((item,), plan, dry_run=False)


def test_global_compatibility_requires_real_finalization_before_effects(tmp_path):
    home, skills, _, _, plan, _, _, _ = fixture(tmp_path)
    target = home / ".codex"
    with pytest.raises(ValueError, match="missing finalized Lead"):
        installer._install_codex_legacy_skill_compatibility(
            Path(__file__).resolve().parents[1], home, target, plan, skills, frozenset(), dry_run=False)
    assert not target.exists()


def symlink(link, target):
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as error:
        if getattr(error, "winerror", None) == 1314:
            pytest.skip("directory symlink privilege unavailable")
        raise


def test_canonical_alias_retarget_cannot_authorize_compatibility(tmp_path):
    home, skills, _, _, plan, _, _, _ = fixture(tmp_path)
    original = tmp_path / "original"
    (home / ".agents").rename(original)
    symlink(home / ".agents", original)
    root = Path(__file__).resolve().parents[1]
    authority = installer._linked_runtime_subroots_module(root).LinkedRuntimeSubrootAuthority.bind(
        home / ".agents", scope="global", trusted_global_roots=(home / ".agents",))
    assert authority is not None
    physical_skills = original / "skills"
    owner = installer._CreateOnlyMutablePath(original, installer._InstallTransaction([], enabled=False),
                                             dry_run=False, linked_authority=authority)
    finalized = installer._finalize_canonical_lead_receipt(plan, physical_skills, owner)
    replacement = tmp_path / "replacement"
    shutil.copytree(original, replacement)
    (home / ".agents").unlink()
    symlink(home / ".agents", replacement)
    with pytest.raises(ValueError, match="E_RUNTIME_SUBROOT_IDENTITY_CHANGED"):
        installer._install_codex_legacy_skill_compatibility(root, home, home / ".codex",
            plan, physical_skills, frozenset(), dry_run=False,
            finalized_lead_digest=finalized, canonical_authority=authority)
    assert not (home / ".codex").exists()
    assert (replacement / "skills/lead/retired.py").read_bytes() == b"synthetic retired hook\n"


@pytest.mark.parametrize("existing", (True, False))
def test_foreign_target_drift_after_projection_work_refuses_commit(tmp_path, monkeypatch, existing):
    home, skills, _, lead, plan, owner, _, removed = fixture(tmp_path)
    removed[0].unlink()
    finalized = installer._finalize_canonical_lead_receipt(plan, skills, owner, (removed,))
    target = home / ".codex"
    projection = target / "skills/lead"
    projection.parent.mkdir(parents=True)
    symlink(projection, lead)
    before = projection.lstat().st_ino
    if not existing:
        projection.unlink()
    apply = installer._apply_codex_legacy_skill_projection_plan
    observed = []
    def change_after_projection(*args, **kwargs):
        result = apply(*args, **kwargs)
        observed.append(projection.is_symlink())
        (lead / "foreign").write_bytes(b"preserve foreign post-commit state")
        return result
    monkeypatch.setattr(installer, "_apply_codex_legacy_skill_projection_plan", change_after_projection)
    with pytest.raises(ValueError, match="E_LEGACY_CODEX_SKILL_COLLISION:lead"):
        installer._install_codex_legacy_skill_compatibility(Path(__file__).resolve().parents[1],
            home, target, plan, skills, frozenset(), dry_run=False, finalized_lead_digest=finalized)
    assert observed == [True]
    if existing:
        assert projection.lstat().st_ino == before and projection.resolve() == lead
    else:
        assert not projection.exists() and not projection.is_symlink()
    assert (lead / "foreign").read_bytes() == b"preserve foreign post-commit state"


@pytest.mark.parametrize("drift", ("modified", "same-bytes-replacement", "inserted"))
def test_finalizer_refuses_foreign_receipt_before_noop_or_write(tmp_path, drift):
    _, skills, _, _, plan, owner, _, _ = fixture(tmp_path)
    receipt = skills / installer._LEAD_RECEIPT_NAME
    payload = installer._lead_receipt_bytes(plan.stage.digest)
    if drift != "inserted":
        receipt.write_bytes(payload)
    observed = installer._read_lead_receipt(receipt)
    plan = replace(plan, lead_receipt=installer._LeadReceiptPlan(
        observed, plan.stage.digest, plan.stage.path))
    if drift == "same-bytes-replacement":
        receipt.rename(receipt.with_suffix(".retained"))
    receipt.write_bytes(payload if drift != "modified" else installer._lead_receipt_bytes("0" * 64))
    foreign = installer._read_lead_receipt(receipt)
    with pytest.raises(ValueError, match="E_CANONICAL_LEAD_RECEIPT_DRIFT"):
        installer._finalize_canonical_lead_receipt(plan, skills, owner)
    assert installer._read_lead_receipt(receipt) == foreign


@pytest.mark.parametrize("initial", ("absent", "old"))
def test_finalizer_accepts_only_its_current_receipt_effect_on_reentry(tmp_path, initial):
    _, skills, _, _, plan, owner, _, removed = fixture(tmp_path)
    receipt = skills / installer._LEAD_RECEIPT_NAME
    if initial == "old":
        receipt.write_bytes(installer._lead_receipt_bytes(plan.stage.digest))
    plan = replace(plan, lead_receipt=installer._LeadReceiptPlan(
        installer._read_lead_receipt(receipt), plan.stage.digest, plan.stage.path))
    removed[0].unlink()
    result = installer._finalize_canonical_lead_receipt(plan, skills, owner, (removed,))
    first = installer._read_lead_receipt(receipt)
    assert installer._finalize_canonical_lead_receipt(plan, skills, owner, (removed,)) == result
    assert installer._read_lead_receipt(receipt) == first
    receipt.write_bytes(installer._lead_receipt_bytes("0" * 64))
    foreign = receipt.read_bytes()
    with pytest.raises(ValueError):
        installer._finalize_canonical_lead_receipt(plan, skills, owner, (removed,))
    assert receipt.read_bytes() == foreign


def test_actual_installer_refuses_foreign_receipt_at_finalization(tmp_path, monkeypatch):
    from tests import test_native_role_slice_a as native
    actual = native.installer
    home = tmp_path / "home"
    home.mkdir()
    seeded = native._run_global_installer("codex", home)
    assert seeded.returncode == 0, seeded.stdout + seeded.stderr
    skills = home / ".agents/skills"
    receipt = skills / actual._LEAD_RECEIPT_NAME
    receipt.write_bytes(actual._lead_receipt_bytes(
        actual._tree_sha256(skills / "lead", ignore_runtime_cache=True)))
    foreign = home / "preallocated-foreign-receipt"
    foreign_payload = actual._lead_receipt_bytes("0" * 64)
    foreign.write_bytes(foreign_payload)
    foreign_identity = foreign.stat().st_ino
    retained = home / "displaced-original-receipt"
    finalize = actual._finalize_canonical_lead_receipt
    reached = []
    def replace_before_finalization(plan, target, owner, reclaimed=()):
        assert target == skills
        assert plan.lead_receipt is not None
        assert actual._read_lead_receipt(receipt) == plan.lead_receipt.observed
        reached.append(True)
        receipt.rename(retained)
        foreign.rename(receipt)
        return finalize(plan, target, owner, reclaimed)
    monkeypatch.setattr(actual, "_finalize_canonical_lead_receipt", replace_before_finalization)
    result = native._observe_codex_install(["--global", "--force"], home=home)
    assert reached == [True]
    assert result.returncode == 1 and len(result.errors) == 1
    error = result.errors[0]
    if isinstance(error, actual._InstallFailure):
        error = error.cause
    assert type(error) is ValueError
    assert str(error) == "E_CANONICAL_LEAD_RECEIPT_DRIFT: preflight drift"
    assert receipt.stat().st_ino == foreign_identity
    assert receipt.read_bytes() == foreign_payload
    assert retained.exists()
