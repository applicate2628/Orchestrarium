from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

ARCHIVIST_BINDINGS = (
    ROOT / "src.codex" / "skills" / "knowledge-archivist" / "SKILL.md",
    ROOT / "src.claude" / "agents" / "knowledge-archivist.md",
)

LEAD_BINDINGS = (
    ROOT / "src.codex" / "skills" / "lead" / "SKILL.md",
    ROOT / "src.claude" / "skills" / "lead" / "SKILL.md",
)

CONTROL_SURFACES = (
    ROOT / "src.codex" / "skills" / "lead" / "operating-model.md",
    ROOT / "src.claude" / "agents" / "contracts" / "operating-model.md",
    ROOT / "references-codex" / "periodic-control-matrix.md",
    ROOT / "references-claude" / "periodic-control-matrix.md",
    ROOT / "references-codex" / "ru" / "periodic-control-matrix.md",
    ROOT / "references-claude" / "ru" / "periodic-control-matrix.md",
)

CODEX_ARCHIVIST_INTERFACE = (
    ROOT / "src.codex" / "skills" / "knowledge-archivist" / "agents" / "openai.yaml"
)


def test_archivist_full_registry_mode_separates_structure_from_semantics() -> None:
    required = (
        "Registry Governance Reconciliation (mandatory complete mode)",
        "structural gate",
        "semantic currency",
        "for EVERY current record",
        "Counts, filenames, placement, and syntactically valid status labels never prove semantic currency",
        "Overall `PASS` requires BOTH structural and semantic gates",
        "semantic owner",
        "Never change semantic status merely to make the matrix green",
    )
    for path in ARCHIVIST_BINDINGS:
        text = path.read_text(encoding="utf-8")
        for token in required:
            assert token in text, f"{path}: missing reconciliation contract token {token!r}"


def test_lead_must_consume_every_registry_exception_before_close() -> None:
    required = (
        "Registry reconciliation intake",
        "route every non-consistent semantic row",
        "do not claim the registries current or close the parent item",
        "structural AND semantic gates both return `PASS`",
    )
    for path in LEAD_BINDINGS:
        text = path.read_text(encoding="utf-8")
        for token in required:
            assert token in text, f"{path}: missing Lead reconciliation token {token!r}"


def test_periodic_control_surfaces_name_registry_governance_reconciliation() -> None:
    for path in CONTROL_SURFACES:
        text = path.read_text(encoding="utf-8").casefold()
        assert "registry governance reconciliation" in text or "сверка governance всех реестров" in text, path


def test_codex_archivist_interface_exposes_complete_registry_mode() -> None:
    text = CODEX_ARCHIVIST_INTERFACE.read_text(encoding="utf-8")
    assert "structural plus semantic-currency matrix" in text
    assert "placement-only success" in text


def test_no_parallel_reconciler_skill_or_registry_owner_was_added() -> None:
    for provider in ("src.codex", "src.claude"):
        assert not (ROOT / provider / "skills" / "reconcile-work-items").exists()
        assert not (ROOT / provider / "skills" / "registry-reconciler").exists()
