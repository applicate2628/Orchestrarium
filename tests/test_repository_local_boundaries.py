from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_PRIOR_PAYLOAD = Path(
    "tests/fixtures/canonical-skill-priors/"
    "4e193102e852b25437b3244a4896b31a5e8fc6c5/"
    "architect/agents/openai.yaml"
)


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        capture_output=True,
    )


def test_root_gemini_directory_remains_ignored_as_legacy_local_output() -> None:
    result = _git(ROOT, "check-ignore", "--no-index", "--", ".gemini/session.log")

    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert result.stdout.decode().strip() == ".gemini/session.log"


def test_nested_gemini_directory_remains_visible() -> None:
    result = _git(ROOT, "check-ignore", "--no-index", "--", "nested/.gemini/session.log")

    assert result.returncode == 1, result.stderr.decode(errors="replace")
    assert result.stdout == b""


def test_canonical_prior_payload_is_binary_without_broadening_attribute_scope(
    tmp_path: Path,
) -> None:
    paths = (
        CANONICAL_PRIOR_PAYLOAD.as_posix(),
        "tests/fixtures/canonical-skill-priors/"
        "4e193102e852b25437b3244a4896b31a5e8fc6c5/manifest.json",
        "tests/test_global_lead_accepted_prior.py",
        "src.codex/skills/architect/SKILL.md",
    )
    attributes = _git(ROOT, "check-attr", "text", "--", *paths)
    assert attributes.returncode == 0, attributes.stderr.decode(errors="replace")
    assert attributes.stdout.decode().splitlines() == [
        f"{paths[0]}: text: unset",
        f"{paths[1]}: text: unspecified",
        f"{paths[2]}: text: unspecified",
        f"{paths[3]}: text: unset",
    ]

    repo = tmp_path / "autocrlf-repo"
    repo.mkdir()
    assert _git(repo, "init", "--quiet").returncode == 0
    assert _git(repo, "config", "core.autocrlf", "true").returncode == 0
    (repo / ".gitattributes").write_bytes((ROOT / ".gitattributes").read_bytes())
    source_bytes = (ROOT / CANONICAL_PRIOR_PAYLOAD).read_bytes()
    assert b"\r\n" in source_bytes
    target = repo / CANONICAL_PRIOR_PAYLOAD
    target.parent.mkdir(parents=True)
    target.write_bytes(source_bytes)

    added = _git(repo, "add", ".gitattributes", CANONICAL_PRIOR_PAYLOAD.as_posix())
    assert added.returncode == 0, added.stderr.decode(errors="replace")
    staged = _git(repo, "show", f":{CANONICAL_PRIOR_PAYLOAD.as_posix()}")
    assert staged.returncode == 0, staged.stderr.decode(errors="replace")
    assert hashlib.sha256(staged.stdout).digest() == hashlib.sha256(source_bytes).digest()
    assert staged.stdout == source_bytes
