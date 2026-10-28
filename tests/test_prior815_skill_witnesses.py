"""Exact historical source witnesses, never authority inferred from installed bytes."""
import io
from pathlib import Path
import subprocess
import shutil
import tarfile

import pytest
from tests.test_hook_runtime_transactions import production_installer as installer

ROOT = Path(__file__).resolve().parents[1]
REVISION = "815e9dfbc5932cc13ed1a8b01f44204e4b4d2349"


@pytest.mark.parametrize("name", ("consultant", "github-pr-review-bot", "manual-repo-transfer"))
def test_authenticated_prior_migrates_but_modified_prior_refuses(tmp_path, monkeypatch, name):
    archive = subprocess.check_output([
        "git", "archive", "--format=tar", REVISION, f"src.codex/skills/{name}"], cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(archive)) as package:
        package.extractall(tmp_path / "authenticated", filter="data")
    source = tmp_path / "authenticated/src.codex/skills" / name
    legacy = installer._legacy_tree_sha256(source, ignore_runtime_cache=True)
    strong = installer._tree_sha256(source, ignore_runtime_cache=True)
    assert installer._legacy_factory_identity_v2(name, legacy) == strong
    skills = tmp_path / "target/.agents/skills"
    installed = skills / name
    shutil.copytree(source, installed)
    before = installer._InstallTransaction._observe(installed)
    plan = installer._preflight_canonical_skills(ROOT / "src.codex/skills", skills, root=ROOT)
    try:
        selected = next(item for item in plan.skills if item.name == name)
        assert selected.accepted_prior == strong
        with pytest.raises(RuntimeError, match="controlled rollback"):
            with installer._InstallTransaction([installed], enabled=True) as tx:
                owner = installer._CreateOnlyMutablePath(tmp_path, tx, dry_run=False)
                installer._apply_canonical_skills_plan(plan, skills, owner, root=ROOT)
                assert installer._tree_sha256(installed, ignore_runtime_cache=True) == selected.source_digest
                raise RuntimeError("controlled rollback")
    finally:
        installer._discard_canonical_skills_plan(plan)
    assert installer._InstallTransaction._observe(installed) == before
    path = installed / "SKILL.md"
    path.write_bytes(path.read_bytes() + b"\nuser modification\n")
    modified = installer._InstallTransaction._observe(installed)
    with pytest.raises(ValueError, match="E_ACCEPTED_PRIOR_COLLISION"):
        installer._preflight_canonical_skills(ROOT / "src.codex/skills", skills, root=ROOT)
    assert installer._InstallTransaction._observe(installed) == modified
    # Simulate an ambiguous legacy lookup: the authenticated strong digest
    # must still reject changed installed bytes rather than electing them.
    legacy_hash = installer._legacy_tree_sha256
    def ambiguous_legacy(path, **kwargs):
        return legacy if Path(path) == installed else legacy_hash(path, **kwargs)
    monkeypatch.setattr(installer, "_legacy_tree_sha256", ambiguous_legacy)
    with pytest.raises(ValueError, match="E_ACCEPTED_PRIOR_COLLISION"):
        installer._preflight_canonical_skills(ROOT / "src.codex/skills", skills, root=ROOT)
    assert installer._InstallTransaction._observe(installed) == modified
