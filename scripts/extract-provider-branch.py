#!/usr/bin/env python3
"""Extract a single-provider standalone tree from the monorepo into a directory.

The published provider branches (claude, codex, gemini, qwen) are single-provider
standalone distributions of the monorepo. They drifted because the extraction was
manual. This script makes the transform reproducible.

The transform (verified empirically against the published branches, 2026-06-13):
  - INCLUDE from the source ref (default the monorepo HEAD), per provider:
      src.<provider>/**, references-<provider>/**, shared/**, scripts/**, LICENSE,
      .gitignore, and an ALLOWLIST of self-contained pack docs (DOCS_ALLOW_FROM_MAIN).
  - CLAUDE ONLY: also GENERATE src.claude/skills/agents-X/SKILL.md from each
      src.claude/commands/agents-X.md (a deterministic frontmatter wrapper; the
      standalone Claude pack ships both the command and an auto-discoverable skill).
  - CARRY FORWARD from the published branch (origin/<provider>): the standalone-adapted
      README.md, INSTALL.md, and every docs/** the branch already curated that is NOT in
      DOCS_ALLOW_FROM_MAIN (e.g. agents-mode-reference, provider-runtime-layouts). These are
      hand-maintained for a single-provider install. docs/README.md is the EXCEPTION — it is
      no longer carried but REGENERATED from the monorepo copy (see _regenerate_docs_readme)
      so its index and links reflect what the branch actually ships instead of going stale.
  - EXCLUDE everything else (other providers, the merged root AGENTS.md / CLAUDE.md,
      the maintainer-only shared/references/cross-pack-reconciliation.md manifest,
      root install.py/sh, RELEASE_NOTES.md, tests/, .gitattributes, docs/routing/,
      docs/superpowers/, and any non-allowlisted main doc).

Usage:
  python scripts/extract-provider-branch.py --provider claude --out <dir>
                                            [--source-ref HEAD] [--branch-ref origin/claude]
                                            [--force]

Read-only against git; writes only under --out (which must be empty/nonexistent unless --force).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

PROVIDERS = ("claude", "codex", "gemini", "qwen")

SHARED_PREFIXES = ("shared/", "scripts/")
SHARED_FILES = ("LICENSE", ".gitignore")
MAINTAINER_ONLY_FILES = frozenset({
    "shared/references/cross-pack-reconciliation.md",
})

# Self-contained pack docs pulled FRESH from the monorepo (no links to excluded paths).
# Everything else under docs/ is either carried from the branch (link-consistent standalone
# versions) or excluded (docs/routing/, docs/superpowers/, monorepo-only docs).
DOCS_ALLOW_FROM_MAIN = frozenset({
    "docs/epics.md",
    "docs/decisions.md",
    "docs/dependencies.md",
    "docs/lessons.md",
    "docs/definition-of-ready-done.md",
    "docs/work-item-execution-tracking.md",
    "docs/provider-runtime-layouts.md",
})

# Docs pulled FRESH from the monorepo but post-processed to drop markdown links into
# subtrees a single-provider standalone branch excludes (docs/routing/, docs/superpowers/).
# The link TEXT is kept; only the broken link target is unwrapped. Without this the monorepo
# copy would carry a dead link, which is why these docs were previously frozen as stale
# branch copies (and silently fell behind the monorepo).
_EXCLUDED_LINK_RE = re.compile(r"\[([^\]]+)\]\((?:\.?/)?(?:routing|superpowers)/[^)]*\)")


def _delink_excluded(content: bytes) -> bytes:
    return _EXCLUDED_LINK_RE.sub(r"\1", content.decode("utf-8")).encode("utf-8")


_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def _delink_dead(line: str, out: Path) -> str:
    """Delink (keep the text, drop the `(target)`) any RELATIVE markdown link
    whose target does not resolve to a file/dir actually present in the standalone
    tree `out`. A standalone branch ships only ONE provider's src.<p>/ +
    references-<p>/ and excludes subtrees (docs/routing/, docs/superpowers/), so a
    monorepo link into a sibling provider's subtree or an excluded subtree is dead
    on this branch. Absolute/anchor/external links (http, #, mailto:) are kept."""
    def repl(m: "re.Match[str]") -> str:
        text, target = m.group(1), m.group(2)
        if target.startswith(("http://", "https://", "#", "mailto:")):
            return m.group(0)
        # resolve the PATH part only — a `#fragment` / `?query` on a link to a
        # doc that DOES ship must not be false-delinked (the target file exists,
        # only the anchor is appended). A pure fragment/query is kept as-is.
        path_part = target.split("#", 1)[0].split("?", 1)[0]
        if not path_part:
            return m.group(0)
        # the README lives at out/docs/README.md, so targets resolve relative to out/docs/
        try:
            if (out / "docs" / path_part).resolve().exists():
                return m.group(0)
        except (OSError, ValueError):
            pass
        return text  # dead link -> keep the descriptive text only
    return _MD_LINK_RE.sub(repl, line)


def _regenerate_docs_readme(monorepo_readme: bytes, out: Path, provider: str) -> bytes:
    """Rebuild docs/README.md for a standalone branch from the MONOREPO copy, so
    it reflects what the branch ACTUALLY ships — not a frozen branch copy that
    silently falls behind (gap 3). Two passes:
      1) the "Current docs in this branch:" list: drop a bullet whose target is an
         excluded subdir or a top-level doc not shipped under out/docs/;
      2) EVERY markdown link (whole file): delink any target that does not resolve
         in the standalone tree `out` (sibling-provider subtrees, excluded subtrees)
         — this is what kept the old regeneration shipping dead cross-provider
         links in the top "Use it together with:" section.
    The intro line is also rewritten from the monorepo phrasing to the standalone
    pack it actually is."""
    shipped_docs = {p.name for p in (out / "docs").glob("*.md")} if (out / "docs").is_dir() else set()
    text = monorepo_readme.decode("utf-8")
    kept: list[str] = []
    in_current = False
    for line in text.split("\n"):
        if line.startswith("Current docs in this branch:"):
            in_current = True
            kept.append(line)
            continue
        if in_current and line.startswith("## "):
            in_current = False
        if in_current and line.lstrip().startswith("- ["):
            m = re.search(r"\]\(([^)]+)\)", line)
            if m and ("/" in m.group(1) or m.group(1) not in shipped_docs):
                continue  # excluded subdir or unshipped top-level doc -> drop bullet
        kept.append(_delink_dead(line, out))
    result = "\n".join(kept)
    result = result.replace(
        "This directory is the branch-level docs surface for the Orchestrarium monorepo common layer.",
        f"This directory is the docs surface for the standalone {provider.capitalize()} pack.",
    )
    return result.encode("utf-8")


# path -> transform applied to the monorepo copy before writing into the standalone tree.
DOCS_FROM_MAIN_TRANSFORMED = {
    "docs/agents-mode-reference.md": _delink_excluded,
}

# Standalone files that MUST be carried from the published branch (fail closed if missing).
REQUIRED_CARRY = ("README.md", "INSTALL.md")

COMMAND_RE = re.compile(r"^src\.claude/commands/(agents-[\w-]+)\.md$")

_YAML_LEADING_INDICATORS = set("-?:,[]{}#&*!|>'\"%@` ")


def git(*args: str) -> str:
    # core.quotepath=false so non-ASCII tracked paths are emitted literally (not C-quoted).
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def ref_exists(ref: str) -> bool:
    try:
        git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
        return True
    except RuntimeError:
        return False


def tracked_paths(ref: str) -> list[str]:
    return [p for p in git("ls-tree", "-r", "--name-only", ref).splitlines() if p]


def show(ref: str, path: str) -> bytes:
    result = subprocess.run(["git", "-c", "core.quotepath=false", "show", f"{ref}:{path}"], capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"git show {ref}:{path} failed: {result.stderr.decode(errors='replace').strip()}")
    return result.stdout


def include_from_main(path: str, provider: str) -> bool:
    if path in MAINTAINER_ONLY_FILES:
        return False
    if path.startswith((f"src.{provider}/", f"references-{provider}/", *SHARED_PREFIXES)):
        return True
    if path in SHARED_FILES:
        return True
    return path in DOCS_ALLOW_FROM_MAIN or path in DOCS_FROM_MAIN_TRANSFORMED


def command_tagline(text: str) -> str:
    """The one-line description = first non-empty, non-heading line after the H1."""
    lines = text.splitlines()
    seen_h1 = False
    for line in lines:
        stripped = line.strip()
        if not seen_h1:
            if stripped.startswith("# "):
                seen_h1 = True
            continue
        if not stripped or stripped.startswith("#"):
            continue
        return stripped
    for line in lines:
        if line.strip().startswith("# "):
            return line.strip()[2:].strip()
    return ""


def yaml_scalar(value: str) -> str:
    """Emit a YAML-safe scalar: a bare plain scalar when safe, else a JSON-encoded
    (valid YAML flow) scalar. Keeps the established bare form for ordinary descriptions
    while correctly quoting one that contains a YAML indicator (e.g. an embedded ': ')."""
    if (value
            and value[0] not in _YAML_LEADING_INDICATORS
            and ": " not in value
            and " #" not in value
            and not value.endswith((":", " "))
            and "\n" not in value and "\t" not in value):
        return value
    return json.dumps(value, ensure_ascii=False)


def skill_from_command(name: str, command_text: str) -> str:
    desc = yaml_scalar(command_tagline(command_text))
    frontmatter = f"---\nname: {name}\ndescription: {desc}\ndisable-model-invocation: true\n---\n"
    return frontmatter + command_text


def write_file(out: Path, rel: str, content: bytes) -> None:
    dest = out / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)


def extract(provider: str, source_ref: str, branch_ref: str, out: Path) -> dict[str, int]:
    if not ref_exists(branch_ref):
        raise RuntimeError(f"branch-ref does not resolve: {branch_ref} (fetch it, or pass --branch-ref)")
    out.mkdir(parents=True, exist_ok=True)
    counts = {"copied": 0, "skills_generated": 0, "carried": 0}

    source_paths = tracked_paths(source_ref)
    branch_paths = tracked_paths(branch_ref)

    # 1. include provider subtree + shared + allowlisted docs from the monorepo
    for path in source_paths:
        if include_from_main(path, provider):
            content = show(source_ref, path)
            transform = DOCS_FROM_MAIN_TRANSFORMED.get(path)
            if transform:
                content = transform(content)
            write_file(out, path, content)
            counts["copied"] += 1

    # 2. claude only: generate a skill per agents-* command
    if provider == "claude":
        for path in source_paths:
            m = COMMAND_RE.match(path)
            if m:
                name = m.group(1)
                skill = skill_from_command(name, show(source_ref, path).decode("utf-8"))
                write_file(out, f"src.claude/skills/{name}/SKILL.md", skill.encode("utf-8"))
                counts["skills_generated"] += 1

    # 3. carry from the published branch: required standalone files + the branch's
    #    curated docs that are not pulled fresh from main (link-consistent versions).
    #    docs/README.md is EXCLUDED from the carry — it is regenerated from the
    #    monorepo copy in step 4 so its "Current docs" index cannot go stale (gap 3).
    carry = list(REQUIRED_CARRY) + [
        p for p in branch_paths
        if p.startswith("docs/")
        and p != "docs/README.md"
        and p not in DOCS_ALLOW_FROM_MAIN
        and p not in DOCS_FROM_MAIN_TRANSFORMED
    ]
    for rel in carry:
        if rel in REQUIRED_CARRY and rel not in branch_paths:
            raise RuntimeError(f"required standalone file missing on {branch_ref}: {rel} (cannot build a complete tree)")
        write_file(out, rel, show(branch_ref, rel))
        counts["carried"] += 1

    # 4. GENERATE docs/README.md from the monorepo copy, rebuilding its
    #    "Current docs in this branch:" list from the docs actually shipped under
    #    out/docs/ (top-level only — excluded subtrees like docs/routing/ are not
    #    carried, so their bullets are dropped). This replaces the old frozen
    #    branch copy that silently fell behind the monorepo.
    write_file(out, "docs/README.md",
               _regenerate_docs_readme(show(source_ref, "docs/README.md"), out, provider))
    counts["carried"] += 1

    return counts


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Extract a single-provider standalone tree from the monorepo.")
    parser.add_argument("--provider", required=True, choices=PROVIDERS)
    parser.add_argument("--out", required=True, type=Path, help="Output dir (must be empty/nonexistent unless --force).")
    parser.add_argument("--source-ref", default="HEAD", help="Monorepo ref to extract from. Default HEAD.")
    parser.add_argument("--branch-ref", default=None, help="Published branch ref to carry standalone files from. Default origin/<provider>.")
    parser.add_argument("--force", action="store_true", help="Allow writing into a non-empty --out (use with care).")
    args = parser.parse_args(argv)

    out = args.out
    if out.exists() and any(out.iterdir()) and not args.force:
        print(f"FAIL: --out is not empty: {out} (use --force to overwrite, or pick a fresh dir)", file=sys.stderr)
        return 1
    if (out / ".git").exists():
        print(f"FAIL: --out looks like a git working tree: {out} (refusing to clobber; use a fresh dir)", file=sys.stderr)
        return 1

    branch_ref = args.branch_ref or f"origin/{args.provider}"
    try:
        counts = extract(args.provider, args.source_ref, branch_ref, out)
    except RuntimeError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"RESULT: extracted {args.provider} -> {out} "
          f"(copied={counts['copied']}, skills_generated={counts['skills_generated']}, carried={counts['carried']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
