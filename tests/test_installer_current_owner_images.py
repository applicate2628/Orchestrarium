"""Current owner images survive admitted updates; foreign state stays rejected."""
from contextlib import nullcontext
import os
from pathlib import Path
import shutil

import pytest

from test_provider_prompt_projections import (
    ROOT, _load_installer, _receipted_predecessor, _sha,
)


@pytest.mark.parametrize("state", ("complete", "cache-retired", "foreign-bytes", "other-tree", "other-predecessor"))
def test_predecessor_content_update_requires_its_original_and_current_owner(
    tmp_path: Path, state: str,
) -> None:
    installer, canonical, peer, desired = _receipted_predecessor(tmp_path)
    source = tmp_path / "source-skills"
    source.mkdir()
    shutil.copytree(ROOT / "src.codex/skills/lead", source / "lead")
    cache = canonical / "lead/scripts/__pycache__/provider_prompt.cpython-315.pyc"
    if state == "cache-retired":
        cache.parent.mkdir(exist_ok=True)
        cache.write_bytes(b"old ordinary runtime cache")
    plan = installer._preflight_canonical_skills(source, canonical, root=ROOT, claude_transport_root=peer)
    members = ("scripts/provider_prompt.py", "shared/provider-prompt-projections.v1.json")
    lead = canonical / "lead"
    other = tmp_path / "other-lead"
    if state == "other-tree":
        shutil.copytree(lead, other)
    if state == "other-predecessor":
        # Equal bytes with another object identity cannot inherit the captured predecessor.
        leaf = lead / members[0]
        replacement = tmp_path / "replacement.py"
        replacement.write_bytes(leaf.read_bytes())
        old_identity = leaf.stat().st_ino
        os.replace(replacement, leaf)
        assert leaf.stat().st_ino != old_identity
    before = installer._InstallTransaction._observe(canonical)
    peer_before = installer._InstallTransaction._observe(peer.parent)
    try:
        paths = [canonical, other] if state == "other-tree" else [canonical]
        complete = state in {"complete", "cache-retired"}
        rollback = (nullcontext() if complete
                    else pytest.raises(RuntimeError, match="test-requested rollback"))
        with rollback, installer._InstallTransaction(paths, enabled=True) as transaction:
            owner = installer._CreateOnlyMutablePath(tmp_path, transaction, dry_run=False)
            destination = other if state == "other-tree" else lead
            identities = {relative: (destination / relative).stat().st_ino for relative in members}
            for relative in members:
                payload = (plan.stage.path / relative).read_bytes()
                transaction.transform_scalar(destination / relative, None, lambda _old, data=payload: data, owner)
            assert {relative: (destination / relative).stat().st_ino for relative in members} == identities
            if state == "cache-retired":
                owner.remove_exact_file(cache.relative_to(tmp_path), _sha(cache.read_bytes()))
            restore = {}
            if state == "foreign-bytes":
                leaf = lead / members[0]
                restore[leaf] = leaf.read_bytes()
                leaf.write_bytes(restore[leaf][:-1] + b"!")
            elif state == "other-tree":
                # A complete foreign postimage plus an unrelated owned effect is still unowned.
                for relative in members:
                    leaf = lead / relative
                    restore[leaf] = leaf.read_bytes()
                    leaf.write_bytes((plan.stage.path / relative).read_bytes())
            try:
                if complete:
                    installer._apply_canonical_skills_plan(plan, canonical, owner, root=ROOT, claude_transport_root=peer)
                    installer._finalize_canonical_lead_receipt(plan, canonical, owner)
                    transaction.commit()
                else:
                    with pytest.raises(ValueError, match="owned Lead content drift|preflight drift lead"):
                        installer._apply_canonical_skills_plan(plan, canonical, owner, root=ROOT, claude_transport_root=peer)
                    assert installer._InstallTransaction._observe(peer.parent) == peer_before
            finally:
                # Restore only this test's injected drift so the original transaction can settle.
                for leaf, payload in restore.items():
                    leaf.write_bytes(payload)
            if not complete:
                raise RuntimeError("test-requested rollback")
        if complete:
            assert (peer / "provider_prompt.py").read_bytes() == (ROOT / "scripts/provider_prompt.py").read_bytes()
            assert {relative: (lead / relative).stat().st_ino for relative in members} == identities
            if state == "cache-retired":
                assert not cache.exists()
        else:
            assert installer._InstallTransaction._observe(canonical) == before
    finally:
        installer._discard_canonical_skills_plan(plan)
        shutil.rmtree(desired.path)



@pytest.mark.skipif(os.name != "nt", reason="Windows replacement security witnesses")
@pytest.mark.parametrize("commit", (False, True))
def test_retired_file_uses_security_image_from_owned_tree_replacement(
    tmp_path: Path, commit: bool,
) -> None:
    installer = _load_installer()
    target = tmp_path / "lead"
    source = tmp_path / "source"
    target.mkdir()
    (target / "obsolete.txt").write_bytes(b"owned obsolete file\n")
    (target / "kept.txt").write_bytes(b"retained file\n")
    shutil.copytree(target, source)
    (source / "added.txt").write_bytes(b"new file forces staged tree publication\n")
    rollback = nullcontext() if commit else pytest.raises(RuntimeError, match="test-requested rollback")
    with rollback, installer._InstallTransaction([target], enabled=True) as transaction:
        before = transaction._windows_tree_security(target, installer._InstallTransaction._observe(target))
        owner = installer._CreateOnlyMutablePath(tmp_path, transaction, dry_run=False)
        owner.replace_exact_tree(Path("lead"), installer._tree_sha256(target), source)
        obsolete = target / "obsolete.txt"
        admitted = installer._admitted_mutation_image(transaction, obsolete)
        assert admitted[obsolete].security is not None
        owner.remove_exact_file(Path("lead/obsolete.txt"), _sha(b"owned obsolete file\n"))
        removal = next(effect for effect in transaction._effects if effect.path == obsolete)
        assert removal.before == admitted
        transaction.assert_effect_current(removal)
        assert not obsolete.exists()
        if commit:
            transaction.commit()
        else:
            raise RuntimeError("test-requested rollback")
    if commit:
        assert not (target / "obsolete.txt").exists()
        assert (target / "added.txt").read_bytes() == (source / "added.txt").read_bytes()
    else:
        assert installer._InstallTransaction._image_matches(target, before)
