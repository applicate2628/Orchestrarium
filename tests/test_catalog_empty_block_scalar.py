"""Empty block scalars must not consume sibling identity in either parser mode."""
from pathlib import Path
import runpy
import pytest
PARSE = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/validate-codex-skill-catalog-budget.py"))["_parse_frontmatter_scalars"]

@pytest.mark.parametrize("runtime_metadata", [False, True])
@pytest.mark.parametrize("marker", [">", ">-", ">+", "|", "|-", "|+"])
@pytest.mark.parametrize("gap", ["", "\n   \n"])
def test_empty_block_preserves_sibling_identity(runtime_metadata, marker, gap):
    parsed = PARSE(f"description: {marker}\n{gap}name: alpha\n", runtime_metadata=runtime_metadata)
    assert parsed["name"] == "alpha"
    assert not parsed["description"].strip()  # Existing chomp behavior is unchanged.

@pytest.mark.parametrize("runtime_metadata", [False, True])
def test_indented_key_text_remains_scalar_content(runtime_metadata):
    parsed = PARSE("description: >-\n  first line\n  name: body text\nname: alpha\n", runtime_metadata=runtime_metadata)
    assert parsed == {"description": "first line name: body text", "name": "alpha"}
