"""CABIG01-07 guards for generic C ABI guidance and runtime role contracts."""

from __future__ import annotations

from pathlib import Path
import re

import pytest


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "shared" / "references" / "c-abi-external-adapter-boundaries.md"
RUSSIAN_MIRROR = ROOT / "shared" / "references" / "ru" / REFERENCE.name
REFERENCE_REL = "shared/references/c-abi-external-adapter-boundaries.md"

ROLE_PAIRS = {
    "architect": (
        ROOT / "src.codex" / "skills" / "architect" / "SKILL.md",
        ROOT / "src.claude" / "skills" / "architect" / "SKILL.md",
    ),
    "architecture-reviewer": (
        ROOT / "src.codex" / "skills" / "architecture-reviewer" / "SKILL.md",
        ROOT / "src.claude" / "agents" / "architecture-reviewer.md",
    ),
    "toolchain-engineer": (
        ROOT / "src.codex" / "skills" / "toolchain-engineer" / "SKILL.md",
        ROOT / "src.claude" / "agents" / "toolchain-engineer.md",
    ),
}

BLOCK_BEGIN = "<!-- CABI-EXTERNAL-ADAPTER:BEGIN -->"
BLOCK_END = "<!-- CABI-EXTERNAL-ADAPTER:END -->"
SEMANTIC_IDS = (
    "CABI.scope",
    "CABI.not-wire",
    "CABI.contract-shape",
    "CABI.data",
    "CABI.ownership",
    "CABI.bulk",
    "CABI.callbacks",
    "CABI.compatibility",
    "CABI.concretization",
    "CABI.acceptance",
)


def _read(path: Path) -> str:
    if not path.is_file():
        pytest.fail(f"missing required surface: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def _fold(text: str) -> str:
    return " ".join(text.casefold().split())


def _role_block(path: Path) -> str:
    text = _read(path)
    assert text.count(BLOCK_BEGIN) == 1, f"missing or duplicate C ABI block in {path}"
    assert text.count(BLOCK_END) == 1, f"missing or duplicate C ABI block in {path}"
    return text.split(BLOCK_BEGIN, 1)[1].split(BLOCK_END, 1)[0].strip()


def test_cabig01_reference_is_generic_and_neutral() -> None:
    text = _read(REFERENCE)
    folded = text.casefold()

    assert "adapter_get_api" in text
    assert not re.search(r"(?i)(?:^|[^a-z])[a-z]:[\\/]", text)
    for residue in ("vfem", "mesher", "work-items/", "codex", "claude"):
        assert residue not in folded, f"project/provider residue leaked into reference: {residue}"


def test_cabig02_reference_does_not_choose_named_compilers() -> None:
    folded = _fold(_read(REFERENCE))
    forbidden = ("clang-cl", "icx-cl", "clang++", "icpx", "gcc", "g++", "cl.exe", "msvc")

    for compiler_name in forbidden:
        assert compiler_name not in folded, f"named compiler policy leaked: {compiler_name}"


def test_cabig03_repository_local_concretization_has_required_fields() -> None:
    text = _read(REFERENCE)
    section = text.split("## Repository-local concretization", 1)[1]
    section = section.split("\n## ", 1)[0]

    required_fields = (
        "Boundary owner and consumers",
        "Supported platforms and architectures",
        "Language baselines",
        "Toolchain matrix",
        "Calling convention and export mechanism",
        "ABI version and support window",
        "Layout and symbol oracles",
        "Compatibility matrix",
        "Lifecycle and unload policy",
    )
    for field in required_fields:
        assert f"- **{field}:**" in section, f"missing concretization field: {field}"


def test_cabig04_runtime_role_contracts_are_identical_and_self_contained() -> None:
    required_contract = (
        "versioned neutral function table",
        "entry point",
        "fixed-width",
        "size and version fields",
        "pointer, count, and stride",
        "allocation and free ownership",
        "context-bearing callbacks",
        "no exceptions cross the abi",
        "stable status",
        "error retrieval",
        "drain before unload",
        "both compatibility directions",
        "negative matrix cells",
        "repository-local concretization",
    )

    for role, (codex_path, claude_path) in ROLE_PAIRS.items():
        codex_block = _role_block(codex_path)
        claude_block = _role_block(claude_path)
        assert codex_block == claude_block, f"{role} trigger/handoff drifted across packs"
        folded = _fold(codex_block)
        assert "replaceable binary adapter" in folded
        assert "independently built, upgraded, or distributed" in folded
        assert REFERENCE_REL not in codex_block
        for contract_term in required_contract:
            assert contract_term in folded, f"{role} runtime contract omits: {contract_term}"


def test_cabig05_architect_hands_off_exactly_two_named_fields() -> None:
    architect_block = _role_block(ROLE_PAIRS["architect"][0])
    fields = re.findall(r"(?m)^- \*\*([^*]+):\*\*", architect_block)

    assert fields == ["C ABI Boundary Contract", "Repository-local concretization"]


def test_cabig06_reviewer_and_toolchain_ownership_stays_distinct() -> None:
    reviewer = _fold(_role_block(ROLE_PAIRS["architecture-reviewer"][0]))
    toolchain = _fold(_role_block(ROLE_PAIRS["toolchain-engineer"][0]))

    assert "this role owns the architecture gate" in reviewer
    assert "toolchain engineer owns repository-local toolchain selection" in reviewer
    assert "this role owns repository-local toolchain selection" in toolchain
    assert "does not redefine the architectural boundary" in toolchain


def test_cabig07_reference_has_one_canonical_copy() -> None:
    candidates = []
    for root in (ROOT / "shared" / "references", ROOT / "references-codex", ROOT / "references-claude"):
        candidates.extend(root.rglob(REFERENCE.name))

    assert sorted(candidates) == sorted((REFERENCE, RUSSIAN_MIRROR))
    russian = _read(RUSSIAN_MIRROR)
    assert "Non-authoritative Russian maintainer mirror" in russian
    assert "../c-abi-external-adapter-boundaries.md" in russian

    marker = re.compile(r'<!-- CABI-SEMANTIC id="([^"]+)" -->')
    assert tuple(marker.findall(_read(REFERENCE))) == SEMANTIC_IDS
    assert tuple(marker.findall(russian)) == SEMANTIC_IDS
    for paths in ROLE_PAIRS.values():
        for path in paths:
            assert REFERENCE_REL not in _read(path)
