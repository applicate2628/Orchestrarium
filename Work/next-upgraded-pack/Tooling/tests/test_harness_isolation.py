"""Acceptance tests for Phase-0 harness isolation (H2 stage + H3 import gate).

Run: python -m pytest Work/next-upgraded-pack/Tooling/tests/test_harness_isolation.py -q
Uses the real N22 bundle as a fixture (it has oracle/ + verifiers/ + a candidate surface).
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

TOOLING = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLING))
import import_candidate_output as ico  # noqa: E402
import stage_provider_root as spr  # noqa: E402

BENCH = TOOLING.parents[2]  # .../benchmarks
N22 = BENCH / "Scenarios-v2" / "N22-numerical-stability-constraint-gauntlet"


@pytest.fixture
def bundle(tmp_path: Path) -> Path:
    dst = tmp_path / "bundle"
    shutil.copytree(N22, dst)
    return dst


def _stage(bundle: Path, tmp_path: Path, canary: bool = False):
    provider = tmp_path / "provider"
    meta = tmp_path / "meta"
    rc = spr.stage(bundle, provider, meta, canary)
    return rc, provider, meta


# ---- H2: staging + structural sentinel ------------------------------------------------------------

def test_sentinel_strips_oracle_and_verifiers(bundle, tmp_path):
    rc, provider, meta = _stage(bundle, tmp_path)
    assert rc == 0
    assert not (provider / "oracle").exists()
    assert not (provider / "verifiers").exists()
    assert (provider / "inputs").is_dir()
    assert (provider / "candidate").is_dir()
    assert (provider / "scenario.yaml").is_file()
    manifest = json.loads((meta / "staging-manifest.json").read_text(encoding="utf-8"))
    assert manifest and all("oracle/" not in r["path"] and "verifiers/" not in r["path"] for r in manifest)


def test_scenario_yaml_unknown_key_stripped(bundle, tmp_path):
    # Inject an unknown metadata key (simulating a future discrimination field leaking into scenario.yaml).
    sc = bundle / "scenario.yaml"
    sc.write_text(sc.read_text(encoding="utf-8") + "\nexpected_winner: ultimate-depth\n", encoding="utf-8")
    rc, provider, meta = _stage(bundle, tmp_path)
    assert rc == 0
    staged = (provider / "scenario.yaml").read_text(encoding="utf-8")
    assert "expected_winner" not in staged
    assert "id:" in staged  # allowlisted keys survive


def test_sentinel_fails_on_forbidden_leftover(bundle, tmp_path):
    # If a forbidden dir is (mis)placed under an allowed tree, staging must hard-fail.
    (bundle / "inputs" / "verifiers").mkdir()
    (bundle / "inputs" / "verifiers" / "leak.py").write_text("x=1", encoding="utf-8")
    rc, provider, meta = _stage(bundle, tmp_path)
    assert rc == 4  # sentinel trip


def test_stage_rejects_source_symlink_to_oracle(bundle, tmp_path):
    # candidate/alias -> ../oracle would leak the answer key under an innocent path (Terra HIGH-3).
    alias = bundle / "candidate" / "alias"
    try:
        alias.symlink_to(bundle / "oracle", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation not permitted on this host")
    rc, provider, meta = _stage(bundle, tmp_path)
    assert rc == 5  # sentinel reparse-point rejection
    assert not provider.exists() or not (provider / "candidate" / "alias").exists()


def test_canary_plants_decoy_and_records_nonce(bundle, tmp_path):
    rc, provider, meta = _stage(bundle, tmp_path, canary=True)
    assert rc == 0
    decoy = provider / "oracle" / "answer-key.json"
    assert decoy.is_file()
    canary = json.loads((meta / "canary.json").read_text(encoding="utf-8"))
    nonce = canary["nonce"]
    # nonce must appear ONLY in the decoy, nowhere else in the provider-visible tree
    for p in provider.rglob("*"):
        if p.is_file() and p != decoy:
            assert nonce not in p.read_text(encoding="utf-8", errors="ignore")


# ---- H3: import gate -------------------------------------------------------------------------------

def _write_candidate_answer(provider: Path) -> None:
    # A legitimate allowed-surface edit (N22 allows candidate/numerical-stability-decision-memo.md).
    (provider / "candidate" / "numerical-stability-decision-memo.md").write_text(
        "# Decision\n\nOption C.\n", encoding="utf-8"
    )


def test_green_import_byte_identical(bundle, tmp_path):
    rc, provider, meta = _stage(bundle, tmp_path)
    _write_candidate_answer(provider)
    out = tmp_path / "out"
    assert ico.import_output(provider, out, meta) == 0
    src = provider / "candidate" / "numerical-stability-decision-memo.md"
    dst = out / "candidate" / "numerical-stability-decision-memo.md"
    assert dst.is_file() and dst.read_bytes() == src.read_bytes()
    manifest = json.loads((meta / "import-manifest.json").read_text(encoding="utf-8"))
    imported = [r for r in manifest if r["disposition"] == "imported"]
    assert any(r["path"].endswith("decision-memo.md") for r in imported)


def test_reject_out_of_surface(bundle, tmp_path):
    rc, provider, meta = _stage(bundle, tmp_path)
    # candidate/README.md is in candidate/ but NOT in allowed_change_surface (must_not_touch).
    (provider / "candidate" / "README.md").write_text("tampered", encoding="utf-8")
    out = tmp_path / "out"
    ico.import_output(provider, out, meta)
    manifest = json.loads((meta / "import-manifest.json").read_text(encoding="utf-8"))
    readme = [r for r in manifest if r["path"].endswith("candidate/README.md")]
    assert readme and readme[0]["disposition"] == "rejected-out-of-surface"


def test_reject_oversize(bundle, tmp_path, monkeypatch):
    rc, provider, meta = _stage(bundle, tmp_path)
    monkeypatch.setattr(ico, "PER_FILE_MAX_BYTES", 16)
    (provider / "candidate" / "numerical-stability-decision-memo.md").write_text("x" * 64, encoding="utf-8")
    out = tmp_path / "out"
    ico.import_output(provider, out, meta)
    manifest = json.loads((meta / "import-manifest.json").read_text(encoding="utf-8"))
    memo = [r for r in manifest if r["path"].endswith("decision-memo.md")]
    assert memo and memo[0]["disposition"] == "rejected-oversize"


def test_reject_ads_unit(tmp_path):
    # ADS names are rejected purely by the relative-path ':' rule (unit-level; no real ADS needed).
    reason = ico.gate_reason(tmp_path, tmp_path / "x", "candidate/answer.md:evil", ["candidate/**"])
    assert reason == "rejected-ads"


def test_symlink_reject_if_supported(bundle, tmp_path):
    rc, provider, meta = _stage(bundle, tmp_path)
    target = provider / "candidate" / "numerical-stability-decision-memo.md"
    link = provider / "candidate" / "witness-ledger.json"
    link.unlink()
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation not permitted on this host")
    out = tmp_path / "out"
    ico.import_output(provider, out, meta)
    manifest = json.loads((meta / "import-manifest.json").read_text(encoding="utf-8"))
    rec = [r for r in manifest if r["path"].endswith("witness-ledger.json")]
    assert rec and rec[0]["disposition"] == "rejected-reparse-point"
