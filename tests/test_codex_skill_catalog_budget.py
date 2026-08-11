"""Wire scripts/validate-codex-skill-catalog-budget.py into the standard test gate.

Codex CLI renders the pack's entire Codex skill catalog into the model-visible
prompt, subject to a runtime-enforced character budget. Runtime string-extraction
evidence (work-items/bugs/2026-07-26-codex-skill-catalog-overflow-is-silent.md)
proved the documented overflow warning never reaches the model-visible prompt or
stderr: growth past the ceiling silently shortens then omits skill entries, with
no signal pointing back at the cause. The pack has no way to learn it outgrew its
own budget except by checking for itself -- that is what this validator does, and
this test file is what makes `pytest tests/` actually run it.

Fail-first discipline: a gate that has never been shown a real overflow proves
nothing (the exact defect this bug is about). The tests below build a synthetic
catalog engineered to CROSS the fail threshold and confirm the validator fires,
before trusting it to stay quiet on anything real.
"""

from __future__ import annotations

import runpy
import subprocess
import sys
import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = REPO_ROOT / "scripts" / "validate-codex-skill-catalog-budget.py"
REPO_SKILLS = REPO_ROOT / "src.codex" / "skills"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def _module():
    return runpy.run_path(str(VALIDATOR))


def _write_skill(root: Path, name: str, description: str) -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        f"---\nname: {name}\ndescription: \"{description}\"\n---\n\n# {name}\n",
        encoding="utf-8",
    )
    return skill_md


def _prompt_input(skills_text: str) -> str:
    return json.dumps(
        [
            {
                "role": "developer",
                "content": [{"type": "input_text", "text": skills_text}],
            }
        ]
    )


def _skills_text(root: Path, rows: list[tuple[str, str]]) -> str:
    rendered = [
        "<skills_instructions>",
        "## Skills",
        "### Skill roots",
        f"- `r0` = `{root.as_posix()}`",
        "### Available skills",
    ]
    rendered.extend(
        f"- {name}: {description} (file: r0/{name}/SKILL.md)"
        for name, description in rows
    )
    rendered.append("</skills_instructions>")
    return "\n".join(rendered)


def test_validator_script_exists() -> None:
    assert VALIDATOR.is_file(), f"validator missing: {VALIDATOR}"


def test_runtime_observation_distinguishes_shortening_from_identity_omission(
    tmp_path: Path,
) -> None:
    repo_skills = tmp_path / "repo-skills"
    installed = tmp_path / "installed"
    _write_skill(repo_skills, "alpha", "full alpha description")
    _write_skill(repo_skills, "beta", "full beta description")
    _write_skill(installed, "alpha", "full alpha description")
    _write_skill(installed, "beta", "full beta description")
    module = _module()

    observed = module["parse_runtime_prompt_input"](
        _prompt_input(
            _skills_text(
                installed,
                [("alpha", "short alpha"), ("beta", "full beta description")],
            )
        ),
        repo_skills,
        installed,
    )

    assert observed.status == "shortened"
    assert observed.total_entries == 2
    assert observed.pack_expected == 2
    assert observed.pack_rendered == 2
    assert observed.shortened_count == 1
    assert observed.omitted_pack == ()


def test_runtime_observation_fails_when_pack_identity_is_omitted(tmp_path: Path) -> None:
    repo_skills = tmp_path / "repo-skills"
    installed = tmp_path / "installed"
    _write_skill(repo_skills, "alpha", "alpha description")
    _write_skill(repo_skills, "beta", "beta description")
    _write_skill(installed, "alpha", "alpha description")
    module = _module()

    observed = module["parse_runtime_prompt_input"](
        _prompt_input(_skills_text(installed, [("alpha", "alpha description")])),
        repo_skills,
        installed,
    )

    assert observed.status == "omitted-pack"
    assert observed.omitted_pack == ("beta",)


def test_runtime_observation_does_not_credit_plugin_or_renamed_identity_collision(
    tmp_path: Path,
) -> None:
    repo_skills = tmp_path / "repo-skills"
    plugin = tmp_path / "plugin"
    pack_runtime = tmp_path / "pack-runtime"
    pack_runtime.mkdir()
    renamed = tmp_path / "renamed"
    _write_skill(repo_skills, "alpha", "pack alpha")
    _write_skill(plugin, "alpha", "plugin alpha")
    _write_skill(renamed, "alpha", "renamed alpha")
    (renamed / "alpha" / "SKILL.md").write_text(
        '---\nname: substitute\ndescription: "renamed alpha"\n---\n',
        encoding="utf-8",
    )
    module = _module()

    plugin_text = _skills_text(plugin, [("plugin:alpha", "plugin alpha")]).replace(
        "plugin:alpha/SKILL.md", "alpha/SKILL.md"
    )
    plugin_collision = module["parse_runtime_prompt_input"](
        _prompt_input(plugin_text),
        repo_skills,
        pack_runtime,
    )
    assert plugin_collision.status == "omitted-pack"
    assert plugin_collision.omitted_pack == ("alpha",)

    renamed_collision = module["parse_runtime_prompt_input"](
        _prompt_input(_skills_text(renamed, [("substitute", "renamed alpha")])),
        repo_skills,
        renamed,
    )
    assert renamed_collision.status == "binding-failure"
    assert renamed_collision.diagnostic == "CATALOG-RUNTIME-BINDING"


def test_runtime_observer_uses_exact_direct_argv_and_typed_execution_failure(
    tmp_path: Path,
) -> None:
    repo_skills = tmp_path / "repo-skills"
    repo_skills.mkdir()
    calls: list[tuple[list[str], dict]] = []

    def runner(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 7, "", "injected failure")

    observed = _module()["observe_runtime_catalog"](
        "codex", repo_skills, repo_skills, runner=runner
    )

    assert calls[0][0] == ["codex", "debug", "prompt-input"]
    assert calls[0][1]["shell"] is False
    assert observed.status == "execution-failure"
    assert observed.diagnostic == "CATALOG-RUNTIME-EXECUTION"


def test_runtime_observation_rejects_ambiguous_or_duplicate_catalogs(tmp_path: Path) -> None:
    repo_skills = tmp_path / "repo-skills"
    installed = tmp_path / "installed"
    _write_skill(repo_skills, "alpha", "alpha description")
    _write_skill(installed, "alpha", "alpha description")
    module = _module()
    block = _skills_text(installed, [("alpha", "alpha description")])

    ambiguous_payload = json.dumps(
        [
            {
                "role": "developer",
                "content": [
                    {"type": "input_text", "text": block},
                    {"type": "input_text", "text": block},
                ],
            }
        ]
    )
    ambiguous = module["parse_runtime_prompt_input"](
        ambiguous_payload, repo_skills, installed
    )
    assert ambiguous.status == "malformed"
    assert ambiguous.diagnostic == "CATALOG-RUNTIME-MALFORMED"

    duplicate = module["parse_runtime_prompt_input"](
        _prompt_input(
            _skills_text(
                installed,
                [("alpha", "alpha description"), ("alpha", "alpha description")],
            )
        ),
        repo_skills,
        installed,
    )
    assert duplicate.status == "binding-failure"
    assert duplicate.diagnostic == "CATALOG-RUNTIME-BINDING"

    traversal = block.replace("r0/alpha/SKILL.md", "r0/../alpha/SKILL.md")
    escaped = module["parse_runtime_prompt_input"](
        _prompt_input(traversal), repo_skills, installed
    )
    assert escaped.status == "binding-failure"
    assert escaped.diagnostic == "CATALOG-RUNTIME-BINDING"


def test_runtime_observer_timeout_is_typed_and_fail_closed(tmp_path: Path) -> None:
    repo_skills = tmp_path / "repo-skills"
    repo_skills.mkdir()

    def runner(argv, **_kwargs):
        raise subprocess.TimeoutExpired(argv, 20)

    observed = _module()["observe_runtime_catalog"](
        "codex", repo_skills, repo_skills, runner=runner
    )
    assert observed.status == "execution-failure"
    assert observed.diagnostic == "CATALOG-RUNTIME-EXECUTION"


@pytest.mark.parametrize(
    ("observation", "expected_code", "expected_marker"),
    (
        (
            ("shortened", "CATALOG-DESCRIPTION-SHORTENED"),
            0,
            "WARNING: CATALOG-DESCRIPTION-SHORTENED",
        ),
        (
            ("omitted-pack", "CATALOG-PACK-IDENTITY-OMITTED"),
            1,
            "FAIL: CATALOG-PACK-IDENTITY-OMITTED",
        ),
        (
            ("unavailable", "CATALOG-RUNTIME-UNAVAILABLE"),
            1,
            "FAIL: CATALOG-RUNTIME-UNAVAILABLE",
        ),
    ),
)
def test_main_runtime_policy_warns_on_shortening_and_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    observation: tuple[str, str],
    expected_code: int,
    expected_marker: str,
) -> None:
    codex_home = tmp_path / "codex-home"
    (codex_home / "skills").mkdir(parents=True)
    repo_skills = tmp_path / "repo-skills"
    _write_skill(repo_skills, "alpha", "alpha description")
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    module = _module()
    runtime_globals = module["main"].__globals__
    runtime_globals["DEFAULT_REPO_SKILLS"] = repo_skills
    runtime_globals["shutil"].which = lambda _name: "codex"
    runtime_globals["discover_entries"] = lambda *_args: []
    runtime_globals["validate"] = lambda *_args, **_kwargs: (True, ["STATIC"])
    status, diagnostic = observation
    runtime_globals["observe_runtime_catalog"] = lambda *_args: module[
        "RuntimeCatalogObservation"
    ](
        status=status,
        diagnostic=diagnostic,
        total_entries=1,
        pack_expected=1,
        pack_rendered=0 if status == "omitted-pack" else 1,
        shortened_count=1 if status == "shortened" else 0,
        shortened_chars=5 if status == "shortened" else 0,
        omitted_pack=("alpha",) if status == "omitted-pack" else (),
    )

    code = module["main"]([])
    output = capsys.readouterr().out

    assert code == expected_code
    assert expected_marker in output
    assert f"RESULT: {'PASS' if expected_code == 0 else 'FAIL'}" in output


# --- Fail-first verification: prove the gate can actually fire -------------


def test_forced_overflow_catalog_fails_the_gate(tmp_path: Path) -> None:
    """Falsify-first: construct a catalog engineered to cross the 90% fail band
    and confirm the validator actually fires. A gate never shown a real overflow
    proves nothing -- this is the check for that."""
    codex_home = tmp_path / "codex_home"
    skills_root = codex_home / "skills"
    repo_skills = tmp_path / "repo_skills"
    repo_skills.mkdir(parents=True)
    agents_skills = tmp_path / "agents_skills"

    # A small context window keeps the ceiling tiny (0.08125 * 2000 ~= 162
    # chars) so a handful of realistic-sized entries reliably overflow it.
    context_window = 2_000
    for i in range(15):
        name = f"forced-overflow-skill-{i:02d}"
        _write_skill(repo_skills, name, "x" * 40)
        _write_skill(skills_root, name, "x" * 40)

    result = _run(
        "--codex-home", str(codex_home),
        "--agents-skills-home", str(agents_skills),
        "--repo-skills", str(repo_skills),
        "--context-window", str(context_window),
    )

    assert result.returncode == 1, result.stdout + result.stderr
    assert "RESULT: FAIL" in result.stdout
    assert "FAIL: rendered catalog is" in result.stdout
    assert ">= fail threshold 90%" in result.stdout


def test_small_synthetic_catalog_stays_quiet(tmp_path: Path) -> None:
    """The converse of the forced-overflow test: a small catalog against a large
    context window must PASS, not merely fail to crash."""
    codex_home = tmp_path / "codex_home"
    skills_root = codex_home / "skills"
    repo_skills = tmp_path / "repo_skills"
    repo_skills.mkdir(parents=True)
    agents_skills = tmp_path / "agents_skills"

    for i in range(3):
        name = f"tiny-skill-{i}"
        _write_skill(repo_skills, name, "short description")
        _write_skill(skills_root, name, "short description")

    result = _run(
        "--codex-home", str(codex_home),
        "--agents-skills-home", str(agents_skills),
        "--repo-skills", str(repo_skills),
        "--context-window", "272000",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT: PASS" in result.stdout


def test_warn_band_is_inclusive_and_non_failing(tmp_path: Path) -> None:
    """The warn band (>= warn-fraction, < fail-fraction) must be visible but must
    NOT fail the gate -- mirrors the WARN/FAIL split already used by
    validate-claude-md.py for the analogous Claude context-budget check."""
    codex_home = tmp_path / "codex_home"
    skills_root = codex_home / "skills"
    repo_skills = tmp_path / "repo_skills"
    repo_skills.mkdir(parents=True)
    agents_skills = tmp_path / "agents_skills"

    # tmp_path depth varies by OS/test-runner, so the fixed (name + path +
    # overhead) portion of a single entry's cost is not knowable in advance.
    # Measure it directly, then choose a context window large enough that the
    # fixed portion is a small slice of the ceiling, and size the description
    # to land the total precisely in the middle of the warn band (80%-90%).
    ceiling_ratio = _module()["CEILING_RATIO"]
    per_entry_overhead = _module()["PER_ENTRY_OVERHEAD_CHARS"]
    probe_path = skills_root / "w" / "SKILL.md"
    fixed = len("w") + len(str(probe_path)) + per_entry_overhead

    ceiling = fixed * 8  # fixed alone is 12.5% of ceiling, plenty of room
    context_window = round(ceiling / ceiling_ratio)
    ceiling = round(context_window * ceiling_ratio)  # re-derive exactly what the script will compute
    target_total = round(ceiling * 0.85)  # middle of the [80%, 90%) warn band
    desc_len = max(0, target_total - fixed)

    _write_skill(repo_skills, "w", "d" * desc_len)
    _write_skill(skills_root, "w", "d" * desc_len)

    result = _run(
        "--codex-home", str(codex_home),
        "--agents-skills-home", str(agents_skills),
        "--repo-skills", str(repo_skills),
        "--context-window", str(context_window),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT: PASS" in result.stdout
    assert "WARNING: rendered catalog is" in result.stdout


# --- Ownership attribution --------------------------------------------------


def test_ownership_attribution_separates_pack_from_external(tmp_path: Path) -> None:
    codex_home = tmp_path / "codex_home"
    skills_root = codex_home / "skills"
    repo_skills = tmp_path / "repo_skills"
    repo_skills.mkdir(parents=True)
    agents_skills = tmp_path / "agents_skills"

    # Pack-owned: name matches something under repo_skills.
    _write_skill(repo_skills, "owned-skill", "pack description")
    _write_skill(skills_root, "owned-skill", "pack description")

    # Personal/marketplace skill installed under CODEX_HOME but NOT shipped by
    # the pack -- must be attributed as "other-codex-home", not "pack".
    _write_skill(skills_root, "personal-skill", "not shipped by the pack")

    # Runtime-created built-in under .system -- must be "system-builtin".
    _write_skill(skills_root / ".system", "imagegen", "built-in, not pack-owned")

    # Cross-tool alias root -- must be "cross-tool".
    _write_skill(agents_skills, "shared-tool-skill", "owned by another tool entirely")

    module = _module()
    entries = module["discover_entries"](codex_home, agents_skills, repo_skills)
    groups = {e.dir_name: e.group for e in entries}

    assert groups["owned-skill"] == "pack"
    assert groups["personal-skill"] == "other-codex-home"
    assert groups["imagegen"] == "system-builtin"
    assert groups["shared-tool-skill"] == "cross-tool"


def test_falsify_entry_set_a_decoy_directory_without_skill_md_is_rejected(tmp_path: Path) -> None:
    """Falsify the entry-set determination: a directory that looks like a skill
    but has no SKILL.md must NOT be counted as an entry."""
    codex_home = tmp_path / "codex_home"
    skills_root = codex_home / "skills"
    repo_skills = tmp_path / "repo_skills"
    repo_skills.mkdir(parents=True)
    agents_skills = tmp_path / "agents_skills"

    _write_skill(repo_skills, "real-skill", "has a SKILL.md")
    _write_skill(skills_root, "real-skill", "has a SKILL.md")

    decoy = skills_root / "decoy-not-a-skill"
    decoy.mkdir(parents=True)
    (decoy / "README.md").write_text("not a SKILL.md", encoding="utf-8")

    module = _module()
    entries = module["discover_entries"](codex_home, agents_skills, repo_skills)
    names = {e.dir_name for e in entries}

    assert "real-skill" in names
    assert "decoy-not-a-skill" not in names
    assert len(entries) == 1


# --- Frontmatter parsing (must match how the SKILL.md files in this repo,
#     and in the cross-tool root, actually declare name/description) --------


def test_quoted_single_line_description_is_parsed() -> None:
    module = _module()
    fm = module["_parse_frontmatter_scalars"]('name: foo\ndescription: "hello world"\n')
    assert fm["name"] == "foo"
    assert fm["description"] == "hello world"


def test_folded_block_scalar_description_matches_yaml_folding() -> None:
    """Regression anchor for the exact calibration this session verified against
    a live ~/.agents/skills root (see the script's module docstring): folded
    block scalars (`description: >-`) must join continuation lines with a
    single space each, matching real cross-tool SKILL.md files."""
    module = _module()
    text = (
        "name: qt-cpp-docs\n"
        "description: >-\n"
        "  Generates standalone Markdown reference documentation for any Qt/C++ source files\n"
        "  Qt Widgets classes, Qt Quick backends, Qt/C++ modules.\n"
    )
    fm = module["_parse_frontmatter_scalars"](text)
    assert fm["description"] == (
        "Generates standalone Markdown reference documentation for any Qt/C++ source files "
        "Qt Widgets classes, Qt Quick backends, Qt/C++ modules."
    )


def test_literal_block_scalar_preserves_newlines() -> None:
    module = _module()
    text = "name: foo\ndescription: |-\n  line one\n  line two\n"
    fm = module["_parse_frontmatter_scalars"](text)
    assert fm["description"] == "line one\nline two"


# --- Fail-closed / SKIP behavior -------------------------------------------


def test_missing_repo_skills_reference_fails_closed(tmp_path: Path) -> None:
    codex_home = tmp_path / "codex_home"
    (codex_home / "skills").mkdir(parents=True)
    missing_repo_skills = tmp_path / "does-not-exist"

    result = _run(
        "--codex-home", str(codex_home),
        "--agents-skills-home", str(tmp_path / "agents"),
        "--repo-skills", str(missing_repo_skills),
    )

    assert result.returncode == 1, result.stdout + result.stderr
    assert "FAIL: repo-skills ownership reference not found" in result.stdout
    assert "RESULT: FAIL" in result.stdout


def test_missing_codex_home_skips_rather_than_fails(tmp_path: Path) -> None:
    """An environment where Codex was never installed/run has nothing to
    measure -- that is not a pack defect, so this must SKIP (exit 0), not FAIL."""
    codex_home = tmp_path / "never-installed"

    result = _run(
        "--codex-home", str(codex_home),
        "--agents-skills-home", str(tmp_path / "agents"),
        "--repo-skills", str(REPO_SKILLS),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "SKIP: no installed Codex skills catalog found" in result.stdout
    assert "RESULT: SKIP" in result.stdout


# --- Real-world checks -------------------------------------------------


def test_pack_own_skill_set_alone_stays_well_under_the_fail_band(tmp_path: Path) -> None:
    """Deterministic, CI-portable sanity check: the pack's OWN shipped skills
    (this repo's src.codex/skills, with no external roots at all) must not by
    themselves already be near the fail band. Uses repo-source SKILL.md paths
    directly, so the absolute path length (and therefore the char-cost
    estimate) is an approximation of the eventual installed-path cost, not a
    byte-exact production simulation -- see the script's module docstring for
    what would make it exact."""
    result = _run(
        "--codex-home", str(REPO_SKILLS.parent),
        "--agents-skills-home", str(tmp_path / "no-agents-skills-here"),
        "--repo-skills", str(REPO_SKILLS),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT: PASS" in result.stdout, result.stdout


def test_live_installed_environment_when_present_stays_quiet() -> None:
    """Optional live check: when this machine has an actual installed Codex
    catalog (CODEX_HOME/skills exists), run the real validator against it and
    confirm production stays quiet -- the "confirm it stays quiet on the real
    one" half of fail-first verification, using genuine installed data instead
    of a synthetic stand-in. Skips when no live install is present (that is an
    environment fact, not a validator defect)."""
    home = Path.home()
    codex_home = home / ".codex" if (home / ".codex" / "skills").is_dir() else None
    if codex_home is None:
        pytest.skip("no live ~/.codex/skills install on this machine")

    result = _run(
        "--codex-home", str(codex_home),
        "--agents-skills-home", str(home / ".agents" / "skills"),
        "--repo-skills", str(REPO_SKILLS),
    )
    assert result.returncode in (0, 1), result.stdout + result.stderr
    assert "RESULT: SKIP" not in result.stdout
    # Report the live number for maintainer visibility without asserting an
    # exact figure (it varies with whatever personal/marketplace skills and
    # runtime built-ins happen to be installed on this machine).
    assert "Fraction of ceiling:" in result.stdout


def test_live_and_created_tracked_text_files_are_lf_only() -> None:
    for path in (VALIDATOR, Path(__file__)):
        raw = path.read_bytes()
        assert b"\r" not in raw, f"tracked text file is not LF-only: {path}"
        raw.decode("utf-8", errors="strict")
