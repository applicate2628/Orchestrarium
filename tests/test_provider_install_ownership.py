"""Ownership is provider-scoped; an observed file is not automatically owned."""
from pathlib import Path
import pytest
from _module_loading_support import load_module

OWNER = load_module(Path(__file__).resolve().parents[1] / "scripts/installation/ownership.py", "provider_ownership_tests")
HASH = "a" * 64


@pytest.mark.parametrize("path", ["../outside", "/absolute", ".claude/../outside",
    ".claude//file", ".claude/file:stream", ".claude/file.", ".claude/file ",
    ".claude\\file", ".codex/config.toml", ".agents/skills/x", "AGENTS.md",
    ".claude/.orche-install.v1.json"])
def test_claude_receipt_cannot_select_other_namespace(path):
    with pytest.raises(ValueError):
        OWNER.encode_record({path: HASH}, "claude", "project")


def test_codec_and_exact_removal_preserve_unknown_or_changed_files():
    files = {".claude/skills/a/SKILL.md": HASH, ".claude/skills/b/SKILL.md": HASH,
             ".claude/skills/c/SKILL.md": HASH, ".claude/skills/d/SKILL.md": HASH}
    record = OWNER.decode_record(OWNER.encode_record(files, "claude", "project"), "claude", "project")
    plan = OWNER.plan_file_removal(record, {".claude/skills/a/SKILL.md": HASH,
        ".claude/skills/b/SKILL.md": "b" * 64, ".claude/skills/c/SKILL.md": None,
        ".claude/user-file.txt": HASH})
    assert plan == {"remove": (".claude/skills/a/SKILL.md",),
                    "preserve": (".claude/skills/b/SKILL.md", ".claude/skills/c/SKILL.md"),
                    "absent": (".claude/skills/d/SKILL.md",)}


def test_reject_wrong_provider_scope_alias_and_duplicate_fields():
    payload = OWNER.encode_record({".claude/a": HASH}, "claude", "project")
    for provider, scope in [("codex", "project"), ("claude", "global")]:
        with pytest.raises(ValueError):
            OWNER.decode_record(payload, provider, scope)
    with pytest.raises(ValueError):
        OWNER.encode_record({".claude/a": HASH, ".claude/A": HASH}, "claude", "project")
    with pytest.raises(ValueError):
        OWNER.decode_record(payload.replace(b'"files":{', b'"files":{},"files":{'), "claude", "project")


def test_codex_project_instruction_is_owned_only_in_project_scope():
    OWNER.encode_record({"AGENTS.md": HASH}, "codex", "project")
    with pytest.raises(ValueError):
        OWNER.encode_record({"AGENTS.md": HASH}, "codex", "global")


def test_empty_receipt_does_not_admit_an_unqualified_host():
    with pytest.raises(ValueError, match="No qualified host-install adapter"):
        OWNER.encode_record({}, "unknown-host", "project")
    with pytest.raises(ValueError):
        OWNER.plan_file_removal([], {})
