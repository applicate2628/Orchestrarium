from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate-slice-a-detached.py"


def _load():
    spec = importlib.util.spec_from_file_location("slice_a_design_currency", VALIDATOR)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_design_currency_resolves_symbols_and_rejects_numeric_python_lines(
    tmp_path: Path,
) -> None:
    module = _load()
    owner = tmp_path / "scripts" / "owner.py"
    owner.parent.mkdir()
    owner.write_text(
        "class Owner:\n    pass\n\ndef first():\n    pass\n\ndef second():\n    pass\n",
        encoding="utf-8",
    )
    design = tmp_path / "design.md"
    design.write_text(
        "# Design\n\n## Exact files and symbols\n"
        "`scripts/owner.py::{Owner,first,second}` and `owner.py::first`\n"
        "Removal contract: remove the zero-caller `scripts/owner.py::gone` "
        "definition; exact-symbol scan must find neither obsolete definition nor caller.\n",
        encoding="utf-8",
    )
    module._validate_design_currency(tmp_path, design)

    design.write_text(
        "# Design\n\nLive citation: `scripts/owner.py:4`.\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="E_SLICE_A_VALIDATION_INCOMPLETE"):
        module._validate_design_currency(tmp_path, design)


def test_design_currency_confines_superseded_owner_terms(
    tmp_path: Path,
) -> None:
    module = _load()
    design = tmp_path / "design.md"
    design.write_text(
        "# Design\n\n### Superseded paragraphs\n"
        "The `_PostMaterializationMutationPlan` claim is superseded.\n\n"
        "## Alternatives rejected\n"
        "The `_PostMaterializationMutationPlan` alternative was rejected.\n",
        encoding="utf-8",
    )
    module._validate_design_currency(tmp_path, design)

    design.write_text(
        "# Design\n\n## Active owner\n"
        "Use `_PostMaterializationMutationPlan` as the active owner.\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="E_SLICE_A_VALIDATION_INCOMPLETE"):
        module._validate_design_currency(tmp_path, design)


def test_design_currency_accepts_explicit_simplify_delete_symbol_inventory(
    tmp_path: Path,
) -> None:
    """Catches rejection of an accepted row whose purpose is deleting its cited owners."""

    module = _load()
    owner = tmp_path / "scripts" / "owner.py"
    owner.parent.mkdir()
    owner.write_text("def live():\n    pass\n", encoding="utf-8")
    design = tmp_path / "design.md"
    design.write_text(
        "# Design\n\n"
        "| Status | File / symbol | Responsibility |\n"
        "| --- | --- | --- |\n"
        "| Simplify/delete | `scripts/owner.py::{gone,obsolete_helper}` | "
        "Delete both machine-authority surfaces. |\n",
        encoding="utf-8",
    )
    module._validate_design_currency(tmp_path, design)

    design.write_text(
        "# Design\n\nLive owner: `scripts/owner.py::gone`.\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unresolved Python symbol citation"):
        module._validate_design_currency(tmp_path, design)
