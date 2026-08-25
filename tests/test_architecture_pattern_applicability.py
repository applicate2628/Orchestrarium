"""Contract tests for the architecture-pattern applicability reference.

The semantic guidance belongs to the canonical English reference.  This test
module owns only stable identifiers, extraction/parity rules, scenario result
classes, and failure oracles.
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "shared/references/architecture-pattern-applicability.md"
RUSSIAN = ROOT / "shared/references/ru/architecture-pattern-applicability.md"
VALIDATOR_DECLARATIONS = (
    ROOT / "src.codex/skills/lead/scripts/validate-skill-pack.py",
    ROOT / "src.claude/agents/scripts/validate-skill-pack.py",
)

APPLICABILITY_IDS = ("AP0", "AP1", "AP2", "AP3", "AP4", "AP5")
GUARD_IDS = (
    "APAT-G01-NO-UNIVERSAL-PRELUDE",
    "APAT-G02-MECHANICS-PRESERVED",
    "APAT-G03-ROLE-SEPARATION",
    "APAT-G04-PROVIDER-PARITY",
    "APAT-G05-INSTALLED-PARITY",
    "APAT-G06-NO-RUNTIME-OVERCLAIM",
    "APAT-G07-C6-CLEAN-STATE",
    "APAT-G08-RU-SEMANTIC-PARITY",
)
FAILURE_IDS = (
    "APAT-E001-CANONICAL-MISSING",
    "APAT-E002-PROJECTION-DRIFT",
    "APAT-E003-ROUTE-MISS",
    "APAT-E004-CARGO-CULT",
    "APAT-E005-DISPOSITION-INCOMPLETE",
    "APAT-E006-INSTALLED-MISSING",
    "APAT-E007-MODEL-FIDELITY",
    "APAT-E008-RU-SEMANTIC-DRIFT",
)


def _load_validator_declaration(path: Path):
    spec = importlib.util.spec_from_file_location(
        f"architecture_pattern_validator_{path.parents[3].name}", path
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_installed_validator_scope_excludes_source_only_maintainer_checks() -> None:
    source_only_prefixes = (
        "@ROOT/shared/references/",
        "@ROOT/references-",
        "@ROOT/src.gemini/",
        "@ROOT/src.qwen/",
        "@ROOT/install.",
        "@ROOT/INSTALL.md",
        "@ROOT/RELEASE_NOTES.md",
        "@ROOT/scripts/agent-run-ledger",
    )
    for declaration in VALIDATOR_DECLARATIONS:
        module = _load_validator_declaration(declaration)
        all_actions = next(actions for scope, actions in module.ACTIONS if scope == "all")
        for action in all_actions:
            assert not any(
                str(value).startswith(source_only_prefixes) for value in action
            ), declaration
            assert action[:2] != ("direct", "curated_registry"), declaration
            assert not any(
                str(value).startswith("src.claude/skills/lead/")
                for value in action
            ), declaration

POSITIVE_SCENARIOS = {
    "APAT-P01-SEMANTIC-BOUNDARY": "route-architect:consider-AP1:no-deployment-inference",
    "APAT-P02-LONG-LIVED-LIFECYCLE": "route-architect:consider-AP2:require-transition-evidence",
    "APAT-P03-READ-WRITE-ASYMMETRY": "route-architect:consider-AP3:no-event-sourcing-inference",
    "APAT-P04-DUAL-WRITE": "route-architect:consider-AP4:require-relay-evidence",
    "APAT-P05-CROSS-OWNER-TRANSACTION": "route-architect:consider-AP5:require-compensation-evidence",
}
NEGATIVE_SCENARIOS = {
    "APAT-N01-COHERENT-DOMAIN": "no-force-architect:reject-AP1",
    "APAT-N02-LINEAR-FLOW": "no-force-architect:reject-AP2",
    "APAT-N03-SIMPLE-CRUD": "no-force-architect:reject-AP3",
    "APAT-N04-NO-DUAL-WRITE": "no-force-architect:reject-AP4",
    "APAT-N05-LOCAL-ATOMIC": "no-force-architect:reject-AP5",
    "APAT-N06-IRREVERSIBLE-INVARIANT": "route-architect:reject-or-defer-AP5",
}
SCENARIO_OUTCOMES = {**POSITIVE_SCENARIOS, **NEGATIVE_SCENARIOS}

AP0_FIELDS = (
    "candidate",
    "trigger-evidence",
    "contraindication-evidence",
    "tradeoffs-cost",
    "composition-interactions",
    "disposition",
    "open-evidence-questions",
)
CARD_FIELDS = ("trigger", "contraindication", "tradeoff", "question", "composition")
CORRESPONDENCE_INVENTORY = (
    *(f"AP0.{field}" for field in AP0_FIELDS),
    *(f"AP{number}.{field}" for number in range(1, 6) for field in CARD_FIELDS),
    *(f"{scenario}.outcome" for scenario in SCENARIO_OUTCOMES),
    *(f"{failure}.meaning" for failure in FAILURE_IDS),
)

BLOCKS = {
    "LEAD-ROUTING": (
        ROOT / "src.codex/skills/lead/SKILL.md",
        ROOT / "src.claude/skills/lead/SKILL.md",
    ),
    "ARCHITECT-DISPOSITION": (
        ROOT / "src.codex/skills/architect/SKILL.md",
        ROOT / "src.claude/skills/architect/SKILL.md",
    ),
    "ARCHITECTURE-REVIEW": (
        ROOT / "src.codex/skills/architecture-reviewer/SKILL.md",
        ROOT / "src.claude/agents/architecture-reviewer.md",
    ),
}

NON_OWNING_ROLES = (
    ROOT / "src.codex/skills/backend-engineer/SKILL.md",
    ROOT / "src.codex/skills/data-engineer/SKILL.md",
    ROOT / "src.codex/skills/reliability-engineer/SKILL.md",
    ROOT / "src.claude/agents/backend-engineer.md",
    ROOT / "src.claude/agents/data-engineer.md",
    ROOT / "src.claude/agents/reliability-engineer.md",
)

SEMANTIC_RECORD = re.compile(
    r'<!--\s*APAT-SEMANTIC\s+id="(?P<id>[^"]+)"\s+'
    r'value="(?P<value>[^"]+)"\s*-->'
)


def _read(path: Path, failure: str) -> str:
    assert path.is_file(), f"{failure}: missing {path.relative_to(ROOT).as_posix()}"
    return path.read_text(encoding="utf-8")


def _extract_unique_block(text: str, block: str, failure: str) -> str:
    begin = f"<!-- APAT-BLOCK:{block}:BEGIN -->"
    end = f"<!-- APAT-BLOCK:{block}:END -->"
    assert text.count(begin) == 1, f"{failure}: {block} BEGIN count={text.count(begin)}"
    assert text.count(end) == 1, f"{failure}: {block} END count={text.count(end)}"
    start = text.index(begin)
    stop = text.index(end, start) + len(end)
    return text[start:stop].replace("\r\n", "\n").replace("\r", "\n")


def _assert_projection_parity(expected: str, actual: str, block: str) -> None:
    assert actual == expected, f"{FAILURE_IDS[1]}: {block} projection differs"


def _parse_semantics(text: str, failure: str) -> dict[str, str]:
    pairs = [(match.group("id"), match.group("value")) for match in SEMANTIC_RECORD.finditer(text)]
    identifiers = [identifier for identifier, _ in pairs]
    duplicates = sorted({identifier for identifier in identifiers if identifiers.count(identifier) > 1})
    assert not duplicates, f"{failure}: duplicate semantic records {duplicates}"
    return dict(pairs)


def _assert_route_contract(records: dict[str, str]) -> None:
    for identifier in POSITIVE_SCENARIOS:
        actual = records[f"{identifier}.outcome"]
        assert actual.startswith("route-architect:"), (
            f"{FAILURE_IDS[2]}: {identifier} observed {actual}"
        )
    for identifier in tuple(NEGATIVE_SCENARIOS)[:5]:
        actual = records[f"{identifier}.outcome"]
        assert actual.startswith("no-force-architect:"), (
            f"{FAILURE_IDS[2]}: {identifier} observed {actual}"
        )
    irreversible = records["APAT-N06-IRREVERSIBLE-INVARIANT.outcome"]
    assert irreversible.startswith("route-architect:"), (
        f"{FAILURE_IDS[2]}: APAT-N06-IRREVERSIBLE-INVARIANT observed {irreversible}"
    )


def _assert_scenario_dispositions(records: dict[str, str]) -> None:
    for identifier, expected in SCENARIO_OUTCOMES.items():
        actual = records[f"{identifier}.outcome"]
        assert actual == expected, (
            f"{FAILURE_IDS[3]}: {identifier} expected {expected}, observed {actual}"
        )


def _assert_disposition_complete(records: dict[str, str], disposition: str) -> None:
    required = (
        *(f"AP0.{field}" for field in AP0_FIELDS),
        *(f"AP{number}.{field}" for number in range(1, 6) for field in CARD_FIELDS),
    )
    missing = [identifier for identifier in required if not records.get(identifier)]
    assert not missing, f"{FAILURE_IDS[4]}: missing disposition fields {missing}"
    for rule in (
        "bounded-context-not-deployment",
        "workflow-not-saga",
        "cqrs-not-event-sourcing",
        "outbox-not-distributed-atomicity-or-exactly-once",
        "saga-not-local-transaction",
    ):
        assert rule in disposition, f"{FAILURE_IDS[4]}: missing composition rule {rule}"


def _assert_complete_semantics(records: dict[str, str], failure: str) -> None:
    expected = set(CORRESPONDENCE_INVENTORY)
    actual = set(records)
    assert actual == expected, (
        f"{failure}: semantic inventory mismatch; "
        f"missing={sorted(expected - actual)} extra={sorted(actual - expected)}"
    )


def _assert_semantic_correspondence(
    english: dict[str, str], russian: dict[str, str]
) -> None:
    _assert_complete_semantics(english, FAILURE_IDS[7])
    _assert_complete_semantics(russian, FAILURE_IDS[7])
    mismatches = sorted(
        identifier
        for identifier in CORRESPONDENCE_INVENTORY
        if english[identifier] != russian[identifier]
    )
    assert not mismatches, f"{FAILURE_IDS[7]}: semantic mismatch {mismatches}"


def _anchor(language: str, identifier: str) -> str:
    suffix = re.sub(r"[^a-z0-9]+", "-", identifier.casefold()).strip("-")
    return f"apat-{language}-{suffix}"


def _semantic_fixture() -> dict[str, str]:
    records = {identifier: f"semantic-{identifier.casefold()}" for identifier in CORRESPONDENCE_INVENTORY}
    records.update(
        {
            "AP3.trigger": "materially-asymmetric-command-query",
            "AP4.contraindication": "reject-when-no-dual-write",
            "AP3.composition": "cqrs-not-event-sourcing",
            "APAT-P01-SEMANTIC-BOUNDARY.outcome": POSITIVE_SCENARIOS[
                "APAT-P01-SEMANTIC-BOUNDARY"
            ],
            "APAT-E001-CANONICAL-MISSING.meaning": "canonical-missing-or-duplicate",
        }
    )
    return records


SEMANTIC_MUTATIONS = (
    ("trigger-threshold", "AP3.trigger", "any-command-query-difference"),
    ("contraindication-negation", "AP4.contraindication", "select-when-no-dual-write"),
    ("composition-non-equivalence", "AP3.composition", "cqrs-may-imply-event-sourcing"),
    ("scenario-disposition", "APAT-P01-SEMANTIC-BOUNDARY.outcome", "no-force-architect"),
    ("failure-meaning", "APAT-E001-CANONICAL-MISSING.meaning", "projection-drift"),
)


def _assert_runtime_fidelity(report_present: bool, static_claim: str) -> None:
    if not report_present:
        assert static_claim == "ASSUMPTION (UNVERIFIED)", (
            f"{FAILURE_IDS[6]}: an unrun pinned fresh-context probe cannot be "
            f"reported as {static_claim!r}"
        )


def test_stable_identifier_inventory() -> None:
    assert APPLICABILITY_IDS == tuple(f"AP{number}" for number in range(6))
    assert len(GUARD_IDS) == 8 and {item[5:8] for item in GUARD_IDS} == {
        f"G{number:02d}" for number in range(1, 9)
    }
    assert len(FAILURE_IDS) == 8 and {item[5:9] for item in FAILURE_IDS} == {
        f"E{number:03d}" for number in range(1, 9)
    }
    assert len(POSITIVE_SCENARIOS) == 5
    assert len(NEGATIVE_SCENARIOS) == 6
    assert len(SCENARIO_OUTCOMES) == 11
    assert len(CORRESPONDENCE_INVENTORY) == len(set(CORRESPONDENCE_INVENTORY)) == 51


def test_canonical_contract_inventory_and_dispositions() -> None:
    text = _read(CANONICAL, FAILURE_IDS[0])
    blocks = {
        block: _extract_unique_block(text, block, FAILURE_IDS[0]) for block in BLOCKS
    }
    disposition = blocks["ARCHITECT-DISPOSITION"]
    records = _parse_semantics(text, FAILURE_IDS[0])
    for identifier in (*APPLICABILITY_IDS, *GUARD_IDS, *FAILURE_IDS, *SCENARIO_OUTCOMES):
        assert identifier in text, f"{FAILURE_IDS[0]}: canonical missing {identifier}"
    _assert_route_contract(records)
    _assert_scenario_dispositions(records)
    _assert_disposition_complete(records, disposition)


def test_source_projection_parity() -> None:
    canonical = _read(CANONICAL, FAILURE_IDS[1])
    for block, paths in BLOCKS.items():
        expected = _extract_unique_block(canonical, block, FAILURE_IDS[1])
        actual = []
        for path in paths:
            role_text = _read(path, FAILURE_IDS[1])
            actual.append(_extract_unique_block(role_text, block, FAILURE_IDS[1]))
        for projection in actual:
            _assert_projection_parity(expected, projection, block)


def test_induced_failure_e001_canonical_missing() -> None:
    text = _read(CANONICAL, FAILURE_IDS[0])
    for block in BLOCKS:
        _extract_unique_block(text, block, FAILURE_IDS[0])
    marker = "<!-- APAT-BLOCK:LEAD-ROUTING:BEGIN -->"
    assert text.count(marker) == 1
    mutated = text.replace(marker, "", 1)
    with pytest.raises(AssertionError, match="APAT-E001-CANONICAL-MISSING"):
        _extract_unique_block(mutated, "LEAD-ROUTING", FAILURE_IDS[0])


def test_induced_failure_e002_projection_drift() -> None:
    canonical = _read(CANONICAL, FAILURE_IDS[1])
    expected = _extract_unique_block(canonical, "LEAD-ROUTING", FAILURE_IDS[1])
    _assert_projection_parity(expected, expected, "LEAD-ROUTING")
    old = "Lead recognises the shape and does not select a pattern"
    assert expected.count(old) == 1
    mutated = expected.replace(old, "Lead recognises the shape and selects a pattern", 1)
    assert "APAT-BLOCK:LEAD-ROUTING:BEGIN" in mutated
    with pytest.raises(AssertionError, match="APAT-E002-PROJECTION-DRIFT"):
        _assert_projection_parity(expected, mutated, "LEAD-ROUTING")


def test_induced_failure_e003_route_miss() -> None:
    records = _parse_semantics(_read(CANONICAL, FAILURE_IDS[0]), FAILURE_IDS[0])
    _assert_route_contract(records)
    mutated = dict(records)
    mutated["APAT-P01-SEMANTIC-BOUNDARY.outcome"] = (
        "no-force-architect:consider-AP1:no-deployment-inference"
    )
    assert all(
        mutated[key] == value
        for key, value in records.items()
        if key != "APAT-P01-SEMANTIC-BOUNDARY.outcome"
    )
    with pytest.raises(AssertionError, match="APAT-E003-ROUTE-MISS"):
        _assert_route_contract(mutated)


def test_induced_failure_e004_cargo_cult_negative_selection() -> None:
    records = _parse_semantics(_read(CANONICAL, FAILURE_IDS[0]), FAILURE_IDS[0])
    _assert_route_contract(records)
    _assert_scenario_dispositions(records)
    mutated = dict(records)
    mutated["APAT-N03-SIMPLE-CRUD.outcome"] = "no-force-architect:select-AP3"
    _assert_route_contract(mutated)
    with pytest.raises(AssertionError, match="APAT-E004-CARGO-CULT"):
        _assert_scenario_dispositions(mutated)


def test_induced_failure_e005_incomplete_disposition() -> None:
    text = _read(CANONICAL, FAILURE_IDS[0])
    disposition = _extract_unique_block(
        text, "ARCHITECT-DISPOSITION", FAILURE_IDS[0]
    )
    records = _parse_semantics(text, FAILURE_IDS[0])
    _assert_route_contract(records)
    _assert_scenario_dispositions(records)
    _assert_disposition_complete(records, disposition)
    mutated = dict(records)
    del mutated["AP3.composition"]
    _assert_route_contract(mutated)
    _assert_scenario_dispositions(mutated)
    with pytest.raises(AssertionError, match="APAT-E005-DISPOSITION-INCOMPLETE"):
        _assert_disposition_complete(mutated, disposition)


def test_selection_ownership_does_not_leak_to_implementation_or_risk_roles() -> None:
    forbidden = (
        "APAT-BLOCK:ARCHITECT-DISPOSITION",
        'APAT-SEMANTIC id="AP1.trigger"',
        'APAT-SEMANTIC id="AP2.trigger"',
        'APAT-SEMANTIC id="AP3.trigger"',
        'APAT-SEMANTIC id="AP4.trigger"',
        'APAT-SEMANTIC id="AP5.trigger"',
    )
    for path in NON_OWNING_ROLES:
        text = _read(path, "APAT-G03-ROLE-SEPARATION")
        hits = [marker for marker in forbidden if marker in text]
        assert not hits, f"APAT-G03-ROLE-SEPARATION: {path.relative_to(ROOT)} owns {hits}"


def test_english_russian_correspondence_inventory() -> None:
    english_text = _read(CANONICAL, FAILURE_IDS[0])
    russian_text = _read(RUSSIAN, FAILURE_IDS[0])
    english = _parse_semantics(english_text, FAILURE_IDS[7])
    russian = _parse_semantics(russian_text, FAILURE_IDS[7])
    _assert_semantic_correspondence(english, russian)

    assert english_text.count("## Russian semantic correspondence") == 1, (
        f"{FAILURE_IDS[7]}: missing or duplicate correspondence matrix"
    )
    for identifier in CORRESPONDENCE_INVENTORY:
        en_anchor = _anchor("en", identifier)
        ru_anchor = _anchor("ru", identifier)
        assert english_text.count(f'id="{en_anchor}"') == 1, (
            f"{FAILURE_IDS[7]}: English anchor count for {identifier}"
        )
        assert russian_text.count(f'id="{ru_anchor}"') == 1, (
            f"{FAILURE_IDS[7]}: Russian anchor count for {identifier}"
        )
        matrix_rows = [
            line
            for line in english_text.splitlines()
            if line.startswith(f"| `{identifier}` |")
            and f"#{en_anchor}" in line
            and f"#{ru_anchor}" in line
        ]
        assert len(matrix_rows) == 1, f"{FAILURE_IDS[7]}: matrix row for {identifier}"


@pytest.mark.parametrize("mutation_id,identifier,replacement", SEMANTIC_MUTATIONS)
def test_semantic_mutations_are_killed_as_e008(
    mutation_id: str, identifier: str, replacement: str
) -> None:
    english = _semantic_fixture()
    russian = dict(english)
    russian[identifier] = replacement
    assert set(russian) == set(english), f"fixture {mutation_id} did not preserve identifiers"
    with pytest.raises(AssertionError, match="APAT-E008-RU-SEMANTIC-DRIFT"):
        _assert_semantic_correspondence(english, russian)


def test_runtime_fidelity_boundary_is_fail_closed() -> None:
    _assert_runtime_fidelity(False, "ASSUMPTION (UNVERIFIED)")
    with pytest.raises(AssertionError, match="APAT-E007-MODEL-FIDELITY"):
        _assert_runtime_fidelity(False, "PASS")
    _assert_runtime_fidelity(True, "PASS")


def test_canonical_runtime_claim_does_not_overstate_static_delivery() -> None:
    text = _read(CANONICAL, FAILURE_IDS[0])
    marker = "<!-- APAT-RUNTIME-FIDELITY: ASSUMPTION (UNVERIFIED) -->"
    assert text.count(marker) == 1, f"{FAILURE_IDS[6]}: canonical runtime marker count"


@pytest.mark.parametrize(
    "provider,installer,source_roles,installed_roles,validator",
    (
        (
            "codex",
            ROOT / "scripts/install-codex.py",
            tuple(paths[0] for paths in BLOCKS.values()),
            (
                Path(".agents/skills/lead/SKILL.md"),
                Path(".agents/skills/architect/SKILL.md"),
                Path(".agents/skills/architecture-reviewer/SKILL.md"),
            ),
            Path(".agents/skills/lead/scripts/validate-skill-pack.py"),
        ),
            (
                "claude",
                ROOT / "scripts/install-claude.py",
                (
                    ROOT / "src.codex/skills/lead/SKILL.md",
                    ROOT / "src.codex/skills/architect/SKILL.md",
                    BLOCKS["ARCHITECTURE-REVIEW"][1],
                ),
            (
                Path(".claude/skills/lead/SKILL.md"),
                Path(".claude/skills/architect/SKILL.md"),
                Path(".claude/agents/architecture-reviewer.md"),
            ),
            Path(".claude/agents/scripts/validate-skill-pack.py"),
        ),
    ),
)
def test_installed_parity_and_validator(
    tmp_path: Path,
    request: pytest.FixtureRequest,
    provider: str,
    installer: Path,
    source_roles: tuple[Path, ...],
    installed_roles: tuple[Path, ...],
    validator: Path,
) -> None:
    declaration = source_roles[0].parent / "scripts/validate-skill-pack.py"
    if provider == "claude":
        declaration = ROOT / "src.claude/agents/scripts/validate-skill-pack.py"
    declaration_text = _read(declaration, FAILURE_IDS[5])
    for marker in ("APAT-G04-PROVIDER-PARITY", "APAT-G05-INSTALLED-PARITY"):
        assert marker in declaration_text, (
            f"{FAILURE_IDS[5]}: {provider} validator declaration missing {marker}"
        )

    target = tmp_path / f"{provider}-target"
    request.addfinalizer(lambda: shutil.rmtree(target) if target.exists() else None)
    installer_arguments = [
        sys.executable,
        str(installer),
        "--target",
        str(target),
        "--force",
        "--allow-unsafe-target",
    ]
    if provider == "claude":
        installer_arguments.append("--no-hypothesis-hook")
    result = subprocess.run(
        installer_arguments,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, (
        f"{FAILURE_IDS[5]}: {provider} installer failed\n{result.stdout}\n{result.stderr}"
    )
    for source, installed in zip(source_roles, installed_roles, strict=True):
        installed_path = target / installed
        assert installed_path.is_file(), (
            f"{FAILURE_IDS[5]}: {provider} missing {installed.as_posix()}"
        )
        assert installed_path.read_bytes() == source.read_bytes(), (
            f"{FAILURE_IDS[5]}: {provider} installed drift for {source.name}"
        )

    installed_validator = target / validator
    validation = subprocess.run(
        [sys.executable, str(installed_validator)],
        cwd=target,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    failure_line = re.search(r"(?m)^\s*FAIL\s{2}", validation.stdout)
    assert validation.returncode == 0 and failure_line is None, (
        f"{FAILURE_IDS[5]}: {provider} installed validator failed\n"
        f"{validation.stdout}\n{validation.stderr}"
    )

    removed_projection = target / installed_roles[1]
    removed_projection.unlink()
    deletion_validation = subprocess.run(
        [sys.executable, str(installed_validator)],
        cwd=target,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    expected_failure = (
        f"APAT-E006-INSTALLED-MISSING: {provider} architect "
        "AP0-AP5 projection file"
    )
    assert deletion_validation.returncode != 0 and expected_failure in deletion_validation.stdout, (
        f"{FAILURE_IDS[5]}: {provider} installed deletion probe missed role/AP evidence\n"
        f"{deletion_validation.stdout}\n{deletion_validation.stderr}"
    )
