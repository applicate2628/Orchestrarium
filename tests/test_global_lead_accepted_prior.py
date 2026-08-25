from __future__ import annotations

import importlib.util
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
INSTALLER_PATH = ROOT / "scripts" / "production_installer.py"
PRE_H2_GLOBAL_LEAD_TREE_SHA256 = (
    "e09377e4cf15c446e2ff19ab160a09835ac6683d51e54a89585625dc1de935ca"
)
CURRENT_GLOBAL_LEAD_TREE_SHA256 = (
    "fd28049deb001bf088b0033e2dcc82ffc372e8257dd8aaf1bc6384d49be328b3"
)


# These seven bytes are pinned historical source blobs, not a version-range
# approximation.  The target omits the current transport set below.
OBSERVED_GLOBAL_LEAD_HISTORICAL_FILES = {
    "external-dispatch.md": (
        "1641fd1c10d501d83891f1bbd27ab93a92eb03b7",
        "src.codex/skills/lead/external-dispatch.md",
    ),
    "operating-model.md": (
        "5587048312ba83ad44da8b7151ae83473932c7bc",
        "src.codex/skills/lead/operating-model.md",
    ),
    "subagent-contracts.md": (
        "1641fd1c10d501d83891f1bbd27ab93a92eb03b7",
        "src.codex/skills/lead/subagent-contracts.md",
    ),
    "scripts/agent-run-ledger.py": (
        "4faedfa13126346b1bac9fc0af49bc0ef5164a45",
        "scripts/agent-run-ledger.py",
    ),
    "scripts/validate-skill-pack.py": (
        "e7a691dea4f1d3cb154d338c63b274ebcd74ee4c",
        "src.codex/skills/lead/scripts/validate-skill-pack.py",
    ),
    "scripts/validate-work-item-state.py": (
        "4faedfa13126346b1bac9fc0af49bc0ef5164a45",
        "scripts/validate-work-item-state.py",
    ),
    "shared/schemas/agent-runs.schema.json": (
        "4faedfa13126346b1bac9fc0af49bc0ef5164a45",
        "shared/schemas/agent-runs.schema.json",
    ),
}
PRE_H2_ONLY_HISTORICAL_FILES = {
    **OBSERVED_GLOBAL_LEAD_HISTORICAL_FILES,
    "scripts/mutate-work-item.py": (
        "e7a691dea4f1d3cb154d338c63b274ebcd74ee4c",
        "scripts/mutate-work-item.py",
    ),
}
OBSERVED_GLOBAL_LEAD_ABSENT_TRANSPORT_FILES = (
    "scripts/external-prompt-governance.md",
    "scripts/invoke-claude-prompt.py",
    "scripts/invoke-codex-prompt.py",
    "scripts/invoke-grok-prompt.py",
    "scripts/invoke-kimi-prompt.py",
    "scripts/provider_prompt.py",
    "scripts/validate-provider-prompt-projections.py",
    "shared/provider-prompt-projections.v1.json",
)

def _load_installer():
    spec = importlib.util.spec_from_file_location(
        "global_lead_accepted_prior_installer", INSTALLER_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _historical_blob(revision: str, source: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{revision}:{source}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout


def test_h2_global_lead_rebaseline_diff_is_only_mutate_work_item() -> None:
    assert set(PRE_H2_ONLY_HISTORICAL_FILES) - set(
        OBSERVED_GLOBAL_LEAD_HISTORICAL_FILES
    ) == {"scripts/mutate-work-item.py"}
    assert hashlib.sha256(
        _historical_blob(*PRE_H2_ONLY_HISTORICAL_FILES["scripts/mutate-work-item.py"])
    ).hexdigest() == "f56ba552c8e7bdc8b814d29d5583d0bce38b5fc2d0581fc4097612e9dbf73da5"
    assert hashlib.sha256(
        (ROOT / "scripts" / "mutate-work-item.py").read_bytes()
    ).hexdigest() == "62e293e047590f8b42408e968d2eaa7f63cd86a5685ae2e12c2642842542740b"


def _seed_exact_observed_global_lead(
    installer,
    skills_root: Path,
    expected_digest: str,
    historical_files: dict[str, tuple[str, str]],
) -> Path:
    lead = skills_root / "lead"
    if lead.exists():
        shutil.rmtree(lead)
    stage = installer._stage_canonical_lead_tree(
        ROOT,
        ROOT / "src.codex" / "skills" / "lead",
        lead / "scripts",
    )
    try:
        shutil.copytree(stage.path, lead)
    finally:
        shutil.rmtree(stage.path, ignore_errors=True)
    for relative, (revision, source) in historical_files.items():
        (lead / relative).write_bytes(_historical_blob(revision, source))
    for relative in OBSERVED_GLOBAL_LEAD_ABSENT_TRANSPORT_FILES:
        (lead / relative).unlink()
    assert (
        installer._tree_sha256(lead, ignore_runtime_cache=True)
        == expected_digest
    )
    return lead


@pytest.mark.parametrize(
    ("expected_digest", "historical_files"),
    (
        (PRE_H2_GLOBAL_LEAD_TREE_SHA256, PRE_H2_ONLY_HISTORICAL_FILES),
        (CURRENT_GLOBAL_LEAD_TREE_SHA256, OBSERVED_GLOBAL_LEAD_HISTORICAL_FILES),
    ),
    ids=("pre-h2", "current-h2"),
)
def test_only_exact_observed_global_lead_tree_is_an_accepted_prior(
    tmp_path: Path,
    expected_digest: str,
    historical_files: dict[str, tuple[str, str]],
) -> None:
    installer = _load_installer()
    skills_root = tmp_path / ".agents" / "skills"
    lead = _seed_exact_observed_global_lead(
        installer, skills_root, expected_digest, historical_files
    )

    plan = installer._preflight_canonical_skills(
        ROOT / "src.codex" / "skills", skills_root, root=ROOT
    )
    try:
        planned_lead = next(skill for skill in plan.skills if skill.name == "lead")
        assert planned_lead.accepted_prior == expected_digest

        owner = installer._CreateOnlyMutablePath(
            tmp_path, installer._InstallTransaction([], enabled=False), dry_run=False
        )
        installer._apply_canonical_skills_plan(plan, skills_root, owner, root=ROOT)
        assert (
            installer._tree_sha256(skills_root / "lead", ignore_runtime_cache=True)
            == planned_lead.source_digest
        )
    finally:
        installer._discard_canonical_skills_plan(plan)

    _seed_exact_observed_global_lead(
        installer, skills_root, expected_digest, historical_files
    )
    with (skills_root / "lead" / "SKILL.md").open("ab") as stream:
        stream.write(b"x")
    with pytest.raises(ValueError, match="E_ACCEPTED_PRIOR_COLLISION: lead"):
        installer._preflight_canonical_skills(
            ROOT / "src.codex" / "skills", skills_root, root=ROOT
        )

    _seed_exact_observed_global_lead(
        installer, skills_root, expected_digest, historical_files
    )
    (skills_root / "lead" / "unrecognized.txt").write_text("extra\n", encoding="utf-8")
    with pytest.raises(ValueError, match="E_ACCEPTED_PRIOR_COLLISION: lead"):
        installer._preflight_canonical_skills(
            ROOT / "src.codex" / "skills", skills_root, root=ROOT
        )
