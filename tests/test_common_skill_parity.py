"""Independent live parity and frozen common-skill snapshot contracts."""
from __future__ import annotations

import importlib
import re
import shutil
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
LIVE_PACKS = ("src.claude", "src.codex")
GENERALIZE_SKILL = "generalize-from-instance"
GENERALIZE_BODY_SHA256 = "7233fcd0d38ccb87e2b95d5f95af3811aa5224e873591eaefd397d3c20b9fea4"


def _runtime():
    return importlib.import_module("scripts.skill_pack_validator_runtime")


def _common_skills(root: Path = ROOT) -> tuple[str, ...]:
    """Return live membership from its sole owner: the shared spine."""
    spine = (root / "shared/AGENTS.shared.md").read_text(encoding="utf-8")
    match = re.search(r"^## Common skills\b.*?\bSet:\s*(.+?)\.", spine, re.S | re.M)
    assert match, "could not find the '## Common skills' Set: line in the spine"
    names = re.findall(r"`\$([a-z][a-z0-9-]+)`", match.group(1))
    assert names, "no `$skill` tokens parsed from the spine Common skills Set line"
    return tuple(names)


def _skill(root: Path, pack: str, name: str) -> Path:
    return root / pack / "skills" / name / "SKILL.md"


def _assert_frontmatter(path: Path, label: str) -> None:
    head = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n").decode(
        "utf-8", "replace"
    )
    assert head.startswith("---\n"), f"{label}: missing YAML frontmatter"
    parts = head.split("\n---\n", 1)
    assert len(parts) == 2, f"{label}: unterminated YAML frontmatter"
    frontmatter = parts[0]
    assert "name:" in frontmatter and "description:" in frontmatter, (
        f"{label}: frontmatter needs name + description"
    )


def _live_common_skill_hashes(root: Path = ROOT) -> dict[str, dict[str, str]]:
    digest = getattr(_runtime(), "common_skill_body_sha256", None)
    assert callable(digest), "canonical public common-skill body digest is missing"
    result: dict[str, dict[str, str]] = {}
    for name in _common_skills(root):
        hashes: dict[str, str] = {}
        for pack in LIVE_PACKS:
            path = _skill(root, pack, name)
            assert path.is_file(), f"live common-skill {name} missing from {pack}"
            _assert_frontmatter(path, f"{pack}/{name}")
            hashes[pack] = digest(path.read_bytes())
        assert len(set(hashes.values())) == 1, (
            f"live common-skill {name} BODY drifted between production packs: {hashes}"
        )
        result[name] = hashes
    return result


def _assert_authoritative_status(root: Path = ROOT) -> None:
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "`src.codex/` — the production Codex provider-pack source" in readme
    assert "`src.claude/` — the production Claude Code provider-pack source" in readme
    assert _runtime().installer_choices_are_supported_production_packs(root)


def _copy_contract_tree(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    for relative_path in (
        "shared/AGENTS.shared.md",
        "README.md",
        "install.py",
    ):
        source = ROOT / relative_path
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    for name in _common_skills():
        for pack in LIVE_PACKS:
            source = _skill(ROOT, pack, name)
            target = _skill(root, pack, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    return root


def _add_live_name(root: Path, name: str) -> None:
    spine = root / "shared/AGENTS.shared.md"
    text = spine.read_text(encoding="utf-8")
    text, replacements = re.subn(
        r"(## Common skills.*?\bSet:\s*)",
        rf"\1`${name}`, ",
        text,
        count=1,
        flags=re.DOTALL,
    )
    assert replacements == 1
    spine.write_text(text, encoding="utf-8")


def test_live_common_skill_bodies_are_byte_identical() -> None:
    hashes = _live_common_skill_hashes()
    assert tuple(hashes) == _common_skills()


def test_generalize_from_instance_is_registered_on_every_common_surface() -> None:
    assert GENERALIZE_SKILL in _common_skills()

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    install = (ROOT / "INSTALL.md").read_text(encoding="utf-8")
    claude_md = (ROOT / "src.claude/CLAUDE.md").read_text(encoding="utf-8")
    token = f"`${GENERALIZE_SKILL}`"
    assert token in readme
    assert token in install
    assert token in claude_md


def test_generalize_from_instance_bodies_match_the_source_pin() -> None:
    digest = _runtime().common_skill_body_sha256
    bodies = {
        pack: _skill(ROOT, pack, GENERALIZE_SKILL).read_bytes()
        for pack in LIVE_PACKS
    }
    assert len(set(bodies.values())) == 1
    assert {digest(body) for body in bodies.values()} == {GENERALIZE_BODY_SHA256}


def test_generalize_from_instance_has_no_private_case_or_absolute_path_anchor() -> None:
    body = _skill(ROOT, "src.codex", GENERALIZE_SKILL).read_text(encoding="utf-8")
    assert "vfem" not in body.casefold()
    private_absolute_paths = re.findall(
        r"(?im)(?:\b[a-z]:[\\/]|/(?:home|users)/[^/\s]+/)",
        body,
    )
    assert not private_absolute_paths


def test_live_add_changes_only_live_membership(tmp_path: Path) -> None:
    root = _copy_contract_tree(tmp_path)
    _add_live_name(root, "fixture-live")
    for pack in LIVE_PACKS:
        path = _skill(root, pack, "fixture-live")
        path.parent.mkdir(parents=True)
        path.write_text(
            "---\nname: fixture-live\ndescription: provider-tailored fixture\n---\nbody\n",
            encoding="utf-8",
        )
    assert "fixture-live" in _live_common_skill_hashes(root)


@pytest.mark.parametrize("pack", LIVE_PACKS)
def test_live_common_skill_mutation_reports_both_hashes(
    tmp_path: Path,
    pack: str,
) -> None:
    root = _copy_contract_tree(tmp_path)
    path = _skill(root, pack, "mathtype-book-page")
    path.write_bytes(path.read_bytes() + b"\nmutated production body\n")
    with pytest.raises(AssertionError) as caught:
        _live_common_skill_hashes(root)
    message = str(caught.value)
    assert "src.claude" in message and "src.codex" in message
    assert "615499de68dc03fccb23954e8ed94662076a9a744a493b71232ebdcce55357be" in message


@pytest.mark.parametrize(
    ("pack", "relative_path", "validator"),
    (
        ("src.codex", "skills/bug-hunting/SKILL.md", _live_common_skill_hashes),
    ),
)
def test_class_specific_frontmatter_fails_in_its_own_owner(
    tmp_path: Path,
    pack: str,
    relative_path: str,
    validator,
) -> None:
    root = _copy_contract_tree(tmp_path)
    path = root / pack / relative_path
    text = path.read_text(encoding="utf-8")
    text, replacements = re.subn(r"^description:.*$", "", text, count=1, flags=re.MULTILINE)
    assert replacements == 1
    path.write_text(text, encoding="utf-8")
    with pytest.raises(AssertionError, match="frontmatter needs name \\+ description"):
        validator(root)


def test_authoritative_status_preserves_production_class() -> None:
    _assert_authoritative_status()


@pytest.mark.parametrize(
    ("relative_path", "needle", "replacement"),
    (
        ("README.md", "`src.codex/` — the production Codex provider-pack source", "`src.codex/` — example"),
        (
            "install.py",
            '"3": ("codex", "claude"),',
            '"3": ("codex",),',
        ),
    ),
)
def test_authoritative_status_mutation_does_not_redefine_production_membership(
    tmp_path: Path,
    relative_path: str,
    needle: str,
    replacement: str,
) -> None:
    root = _copy_contract_tree(tmp_path)
    path = root / relative_path
    text = path.read_text(encoding="utf-8")
    assert needle in text
    path.write_text(text.replace(needle, replacement, 1), encoding="utf-8")
    with pytest.raises(AssertionError):
        _assert_authoritative_status(root)


def test_doc_common_skill_lists_match_the_spine_owner() -> None:
    owner = set(_common_skills())
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    match = re.search(r"Currently shipped:\n(.*?)(?:\n\n|\n#)", readme, re.S)
    assert match, "README.md has no 'Currently shipped:' common-skill list"
    readme_names = set(re.findall(r"^- `\$([a-z][a-z0-9-]+)`", match.group(1), re.M))
    assert readme_names == owner

    claude_md = (ROOT / "src.claude/CLAUDE.md").read_text(encoding="utf-8")
    inline = re.search(
        r"common-skills \((`\$[a-z0-9-]+`(?:,\s*`\$[a-z0-9-]+`)*)\)", claude_md
    )
    assert inline, "src.claude/CLAUDE.md has no inline common-skills enumeration"
    claude_names = set(re.findall(r"`\$([a-z][a-z0-9-]+)`", inline.group(1)))
    assert claude_names == owner
