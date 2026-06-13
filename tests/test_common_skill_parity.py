"""Cross-pack parity for the shared common-skills.

The common-skills (bug-hunting, analyzing-video-bugs, explain-simply,
mathtype-book-page, windows-gui-manual-testing) are shipped per-pack under
src.<provider>/skills/<name>/SKILL.md. The INVARIANT is that the skill BODY (the
methodology, everything after the YAML frontmatter) is byte-identical across all 4
packs — a silent body drift in one pack must be caught. No pack validator
content-checks them today (they assert existence only, and hash the shared
*reference* files, not the skills), so this test closes that gap.

The frontmatter `description:` is deliberately provider-tailored and is NOT required
to match (verified: every pack's body is identical, while Codex ships terser
descriptions and windows-gui names the provider). Only the body parity is enforced.
"""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKS = ("src.claude", "src.codex", "src.gemini", "src.qwen")
COMMON_SKILLS = (
    "bug-hunting",
    "analyzing-video-bugs",
    "explain-simply",
    "mathtype-book-page",
    "windows-gui-manual-testing",
)


def _skill(pack: str, name: str) -> Path:
    return ROOT / pack / "skills" / name / "SKILL.md"


def _body(path: Path) -> bytes:
    """The skill body (after the YAML frontmatter), CRLF-normalized. If there is no
    leading '---' frontmatter fence, the whole file is the body."""
    lines = path.read_bytes().replace(b"\r\n", b"\n").split(b"\n")
    if lines and lines[0].strip() == b"---":
        for i in range(1, len(lines)):
            if lines[i].strip() == b"---":
                return b"\n".join(lines[i + 1:])
    return b"\n".join(lines)


def test_common_skill_bodies_are_byte_identical_across_packs():
    for name in COMMON_SKILLS:
        hashes = {}
        for pack in PACKS:
            p = _skill(pack, name)
            assert p.is_file(), f"common-skill {name} missing from {pack}"
            hashes[pack] = hashlib.sha256(_body(p)).hexdigest()
        distinct = set(hashes.values())
        assert len(distinct) == 1, (
            f"common-skill {name} BODY drifted across packs (methodology must stay identical): {hashes}"
        )


def test_every_common_skill_has_name_and_description_frontmatter():
    for name in COMMON_SKILLS:
        for pack in PACKS:
            p = _skill(pack, name)
            assert p.is_file(), f"common-skill {name} missing from {pack}"
            head = p.read_bytes().replace(b"\r\n", b"\n").decode("utf-8", "replace")
            assert head.startswith("---\n"), f"{pack}/{name}: missing YAML frontmatter"
            fm = head.split("\n---\n", 1)[0]
            assert "name:" in fm and "description:" in fm, f"{pack}/{name}: frontmatter needs name + description"
