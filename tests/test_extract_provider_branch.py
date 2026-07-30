"""Unit tests for the provider-branch extractor's transform logic.

These exercise the pure functions (no git, deterministic). The end-to-end transform
is validated empirically (0 DROPPED files across all 4 provider branches); these
tests guard the inclusion/curation/skill-generation rules against regression.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "extract_provider_branch", ROOT / "scripts" / "extract-provider-branch.py"
)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def inc(path: str, provider: str = "claude") -> bool:
    return mod.include_from_main(path, provider)


# --- inclusion / exclusion (what is pulled FRESH from the monorepo) ----------

def test_claude_includes_pack_paths():
    for p in (
        "src.claude/agents/lead.md",
        "src.claude/commands/agents-status.md",
        "references-claude/README.md",
        "shared/AGENTS.shared.md",
        "scripts/agent-run-ledger.py",
        "LICENSE",
        ".gitignore",
    ):
        assert inc(p), p


def test_claude_excludes_other_providers_merged_root_and_maintainer_only_files():
    for p in (
        "src.codex/skills/lead/SKILL.md",
        "src.gemini/agents/lead.md",
        "references-codex/README.md",
        "AGENTS.md",
        "CLAUDE.md",
        *sorted(mod.MAINTAINER_ONLY_FILES),
        "RELEASE_NOTES.md",
        "tests/test_x.py",
        "install.sh",
        "install.py",
        "install.ps1",
        ".gitattributes",
    ):
        assert not inc(p), p


def test_docs_only_allowlisted_pulled_from_main():
    # self-contained roadmap docs are pulled fresh from main
    assert inc("docs/decisions.md")
    assert inc("docs/work-item-execution-tracking.md")
    assert inc("docs/epics.md")
    # provider-runtime-layouts has no markdown links at all -> pulled fresh from main
    assert inc("docs/provider-runtime-layouts.md")
    # agents-mode-reference is pulled fresh from main but its one excluded-subtree link
    # (docs/routing/) is unwrapped to plain text by a DOCS_FROM_MAIN_TRANSFORMED transform
    assert inc("docs/agents-mode-reference.md")
    # docs/README is EXCLUDED from include-from-main; it is regenerated from the
    # monorepo copy in extract step 4 (_regenerate_docs_readme), not carried
    assert not inc("docs/README.md")
    # external-worker-design is still excluded (it links to routing/ and has no transform)
    assert not inc("docs/external-worker-design.md")
    assert not inc("docs/routing/12-lane-routing-matrix-v1-2026-04-18.md")
    assert not inc("docs/superpowers/plans/x.md")


def test_delink_excluded_unwraps_only_excluded_subtree_links():
    src = (
        "See [`docs/routing/x.md`](routing/x.md) and "
        "[plan](./superpowers/p.md) but keep "
        "[epics](epics.md) and [ext](https://example.com).\n"
    ).encode("utf-8")
    out = mod._delink_excluded(src).decode("utf-8")
    assert "](routing/" not in out and "](./superpowers/" not in out
    assert "`docs/routing/x.md`" in out and "plan" in out          # link TEXT preserved
    assert "[epics](epics.md)" in out                               # in-tree link untouched
    assert "[ext](https://example.com)" in out                      # external url untouched


def test_codex_provider_scopes_correctly():
    assert inc("src.codex/skills/lead/SKILL.md", "codex")
    assert inc("references-codex/README.md", "codex")
    assert not inc("src.claude/agents/lead.md", "codex")
    assert not inc("references-claude/README.md", "codex")
    assert inc("shared/AGENTS.shared.md", "codex")  # shared stays for every provider


# --- skill generation (claude) ----------------------------------------------

def test_command_tagline_after_h1():
    cmd = "# Project Status\n\nShow a compact status dashboard for the current project.\n\n## Steps\n1. x\n"
    assert mod.command_tagline(cmd) == "Show a compact status dashboard for the current project."


def test_command_tagline_falls_back_to_h1_when_no_prose():
    assert mod.command_tagline("# Resume\n\n## Steps\n") == "Resume"


def test_command_tagline_empty_when_no_h1():
    assert mod.command_tagline("no heading here\njust text\n") == ""


def test_yaml_scalar_bare_for_plain_description():
    assert mod.yaml_scalar("Show a compact status dashboard for the current project.") == \
        "Show a compact status dashboard for the current project."


def test_yaml_scalar_quotes_embedded_colon_space():
    # the agents-review-loop case: an embedded ': ' makes a bare scalar invalid YAML
    s = "Run the parallel-review-loop: dispatch three angles."
    out = mod.yaml_scalar(s)
    assert out != s and out.startswith('"') and out.endswith('"')
    import json
    assert json.loads(out) == s


def test_yaml_scalar_quotes_leading_indicator():
    assert mod.yaml_scalar("- a list-looking description")[0] == '"'


def test_skill_from_command_shape_and_valid_yaml():
    cmd = "# Project Status\n\nShow a dashboard.\n\n## Steps\n- a\n"
    skill = mod.skill_from_command("agents-status", cmd)
    assert skill.startswith(
        "---\nname: agents-status\ndescription: Show a dashboard.\ndisable-model-invocation: true\n---\n"
    )
    assert skill.endswith(cmd)  # command body preserved verbatim


def test_skill_from_command_with_colon_description_is_valid_yaml():
    cmd = "# Review Loop\n\nRun the loop: dispatch three angles and converge.\n\n## Steps\n"
    skill = mod.skill_from_command("agents-review-loop", cmd)
    frontmatter = skill.split("---", 2)[1]
    # must round-trip through a YAML parser without error
    try:
        import yaml
        parsed = yaml.safe_load(frontmatter)
        assert parsed["name"] == "agents-review-loop"
        assert parsed["description"] == "Run the loop: dispatch three angles and converge."
    except ImportError:
        # no pyyaml: at least assert the description was quoted (not a bare ': ' scalar)
        assert 'description: "' in frontmatter


def test_command_regex_matches_agents_commands_only():
    assert mod.COMMAND_RE.match("src.claude/commands/agents-status.md")
    assert mod.COMMAND_RE.match("src.claude/commands/agents-qa-session.md")
    assert not mod.COMMAND_RE.match("src.claude/commands/other.md")
    assert not mod.COMMAND_RE.match("src.claude/skills/agents-status/SKILL.md")
