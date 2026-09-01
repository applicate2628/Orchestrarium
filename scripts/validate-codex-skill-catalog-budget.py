#!/usr/bin/env python3
"""Growth gate for the Codex skill catalog's rendered-prompt character budget.

Why this check exists
----------------------
Codex CLI renders a ``## Skills`` catalog
fragment into the model-visible prompt for every entry discovered under
``$CODEX_HOME/skills`` (including the runtime's own auto-created
``.system`` built-ins) plus the cross-tool ``~/.agents/skills`` alias root.
When that fragment would exceed the runtime's own budget, the documented
behavior is to shorten descriptions and then omit entries -- and to *show a
warning* when it does. Runtime string-extraction evidence
(``work-items/bugs/2026-07-26-codex-skill-catalog-overflow-is-silent.md``)
proved the warning never reaches the model-visible prompt or stderr on the
exec path: a capability can silently disappear from what the model is ever
told exists, with no observable signal pointing back at the cause.

Codex 0.147.0 also exposes ``codex debug prompt-input``, a provider-free direct
render of the model-visible input.  The installed-runtime path now treats that
output as authoritative: a missing pack identity fails, description shortening
warns with exact counts, and unavailable or malformed authority fails closed.
The older character estimate remains a portable diagnostic and synthetic
falsification surface; it no longer overrides a successful direct observation.

Where the numbers come from
----------------------------
1. Budget fraction (2%): confirmed by extracting printable strings from the
   installed ``codex.exe`` (win32-x64, codex-cli 0.145.0). The binary embeds
   the literal user-facing strings ``"Exceeded skills context budget of
   2%."`` and ``"Skill descriptions were shortened to fit the 2% skills
   context budget."`` under the ``codex_core_skills::render`` /
   ``codex_skills_extension::render`` symbols. This is an
   installed-dependency surface check, not an inference.
2. Reference ceiling (~22,100 rendered chars at a 272,000-token context
   window): taken from the bug report's causal experiment (overriding the
   context window and observing the ceiling scale linearly). The same
   272,000-token figure is independently confirmed as the *actual* context
   window baked into every current model profile in the installed binary
   (GPT-5.6-Sol/Terra/Luna, GPT-5.5, GPT-5.4, GPT-5.4-Mini all report
   ``"context_window": 272000``) -- so 272,000 is a real production default,
   not a probe-only artifact.
3. Per-entry render cost (name + description + absolute SKILL.md path +
   ``PER_ENTRY_OVERHEAD_CHARS``): calibrated this session by summing
   name+description+absolute-path length across the real, live
   ``~/.codex/skills`` (52 entries) and ``~/.agents/skills`` (11 entries)
   roots and comparing against the bug's independently reported totals
   (8,890 and 5,630 chars respectively). The residual gap was a *constant*
   13.9-14.0 chars/entry on both independently-sized roots -- strong
   evidence of a fixed per-entry template overhead, which is what
   ``PER_ENTRY_OVERHEAD_CHARS`` encodes. This is a smoke-test-calibrated
   estimate, not a byte-exact simulation of the closed-source renderer;
   the resolving step for exact parity is reading
   ``core-skills/src/render.rs`` from the upstream ``openai/codex`` source
   at the pinned tag, which was not locatable via public code search in
   this session.

What the gate keys on (ownership tension, resolved)
----------------------------------------------------
The catalog draws from three groups, only one of which the pack owns:

- ``pack``: entries under ``$CODEX_HOME/skills`` whose name matches a skill
  this repository ships (``src.codex/skills/<name>``). The pack can shrink
  these.
- ``other-codex-home``: entries under ``$CODEX_HOME/skills`` that are NOT
  ``.system`` and do NOT match a pack-shipped name (personal/marketplace
  skills the user installed). Not pack-owned.
- ``system-builtin``: entries under ``$CODEX_HOME/skills/.system``, created
  by the Codex runtime itself. Not pack-owned.
- ``cross-tool``: entries under ``~/.agents/skills``, a cross-tool alias
  root shared with other agent runtimes. Not pack-owned.

All four groups consume the *same* shared rendered-character budget, so the
static estimate reports all four with separate attribution. The pack cannot
always compensate for external growth without destroying its own routing
descriptions; therefore the installed verdict comes from the direct runtime
observation, while the total-fraction estimate remains a loud diagnostic. A
pack-only estimate would still be blind to real degradation risk (the runtime
does not care who owns the bytes it shortens or drops).

Static-estimate bands (portable fallback diagnostics)
------------------------------------------------------
- < 80%: PASS.
- [80%, 90%): WARN (non-failing). 80% is deliberately set at production's
  own long-observed watermark (~79%) so the very next bit of organic growth
  starts raising visibility, long before anything is actually at risk.
- >= 90%: FAIL when no successful authoritative runtime observation owns the
  installed result. A gate at 80% would fire immediately against the original
  calibrated catalog and train maintainers to ignore it. With a successful
  runtime observation, this band remains visible as ``ESTIMATE`` while pack
  identity omission or malformed/unavailable runtime evidence owns failure.
  The 90% estimate retains the original 10-point diagnostic buffer instead of
  being retuned merely to make one installed catalog green.

Operator action when this fires
--------------------------------
WARN: no action required to keep shipping, but budget is closing -- avoid
adding more skill entries without also trimming or splitting existing pack
descriptions.
FAIL from the portable estimate: trim, shorten, split, or deduplicate the pack's OWN skill
descriptions (the ``pack`` group below) until the total fraction drops back
under the WARN band. The ``other-codex-home``/``system-builtin``/
``cross-tool`` groups are reported for attribution but cannot be shrunk by
this pack; if they dominate the growth, that is real information for the
operator (the shared budget shrank for reasons outside pack control), not a
reason to ignore the estimate. Runtime ``CATALOG-PACK-IDENTITY-OMITTED`` and
``CATALOG-RUNTIME-*`` failures require restoring authoritative evidence or the
missing pack identities. ``CATALOG-DESCRIPTION-SHORTENED`` is a loud warning,
not a claim that every shortened routing description remains semantically
equivalent.

Where this runs
----------------
Invoked via ``python -m pytest tests/`` (``tests/test_codex_skill_catalog_
budget.py``) -- the maintainer-run verification surface already named as
this repository's baseline gate, requiring no new CI surface. It also runs
standalone: ``python scripts/validate-codex-skill-catalog-budget.py``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPO_SKILLS = REPO_ROOT / "src.codex" / "skills"

# --- Calibrated constants (see module docstring for provenance) -----------

REFERENCE_CONTEXT_WINDOW_TOKENS = 272_000
REFERENCE_CEILING_CHARS = 22_100
# 22100 / 272000 == 13/160 == 0.08125 exactly.
CEILING_RATIO = REFERENCE_CEILING_CHARS / REFERENCE_CONTEXT_WINDOW_TOKENS

PER_ENTRY_OVERHEAD_CHARS = 14

WARN_FRACTION = 0.80
FAIL_FRACTION = 0.90

FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---", re.DOTALL)
KEY_RE = re.compile(r"^([A-Za-z0-9_-]+):\s*(.*)$")
BLOCK_INDICATORS = (">", ">-", ">+", "|", "|-", "|+")


def _parse_frontmatter_scalars(fm_text: str) -> dict[str, str]:
    """Minimal YAML frontmatter scalar parser.

    Handles plain/quoted single-line values and ``>``/``>-``/``>+``/``|``/
    ``|-``/``|+`` block scalars with standard folding and chomping. This
    repository's SKILL.md frontmatter is flat ``key: value`` pairs only, so
    a full YAML parser is not required (and this repo takes no third-party
    Python dependency -- see scripts/normalize-agents-mode.py and
    scripts/resolve-agents-mode.py, which hand-parse for the same reason).
    """
    lines = fm_text.split("\n")
    result: dict[str, str] = {}
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if not line.strip() or line.startswith("#"):
            i += 1
            continue
        m = KEY_RE.match(line)
        if not m:
            i += 1
            continue
        key, rest = m.group(1), m.group(2).rstrip("\r")
        rest_stripped = rest.strip()
        if rest_stripped in BLOCK_INDICATORS:
            style, chomp = rest_stripped[0], rest_stripped[1:]
            block_lines: list[str] = []
            i += 1
            indent: int | None = None
            while i < n:
                bl = lines[i]
                if bl.strip() == "":
                    block_lines.append("")
                    i += 1
                    continue
                cur_indent = len(bl) - len(bl.lstrip(" "))
                if indent is None:
                    indent = cur_indent
                if cur_indent < indent:
                    break
                block_lines.append(bl[indent:])
                i += 1
            if style == ">":
                parts, buf = [], []
                for bl in block_lines:
                    if bl == "":
                        if buf:
                            parts.append(" ".join(buf))
                            buf = []
                        parts.append("\n")
                    else:
                        buf.append(bl)
                if buf:
                    parts.append(" ".join(buf))
                value = "".join(parts)
            else:
                value = "\n".join(block_lines)
            if chomp == "-":
                value = value.rstrip("\n")
            elif chomp == "+":
                pass
            else:
                value = value.rstrip("\n")
            result[key] = value
            continue
        val = rest_stripped
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        result[key] = val
        i += 1
    return result


def _read_name_description(skill_md: Path) -> tuple[str, str]:
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return skill_md.parent.name, ""
    m = FRONTMATTER_RE.search(text)
    if not m:
        return skill_md.parent.name, ""
    fm = _parse_frontmatter_scalars(m.group(1))
    name = fm.get("name", skill_md.parent.name)
    description = fm.get("description", "")
    return name, description


@dataclass(frozen=True)
class CatalogEntry:
    dir_name: str
    group: str  # "pack" | "other-codex-home" | "system-builtin" | "cross-tool"
    name: str
    description: str
    path: Path

    @property
    def cost(self) -> int:
        return len(self.name) + len(self.description) + len(str(self.path)) + PER_ENTRY_OVERHEAD_CHARS


@dataclass(frozen=True)
class RuntimeCatalogObservation:
    status: str
    diagnostic: str
    total_entries: int = 0
    pack_expected: int = 0
    pack_rendered: int = 0
    shortened_count: int = 0
    shortened_chars: int = 0
    omitted_pack: tuple[str, ...] = ()


ROOT_LINE_RE = re.compile(r"^- `(?P<alias>r\d+)` = `(?P<path>[^`]+)`$", re.MULTILINE)
ENTRY_LINE_RE = re.compile(
    r"^- (?P<header>[^\r\n]+) \(file: (?P<alias>r\d+)/(?P<relative>[^\r\n]+/SKILL\.md)\)$",
    re.MULTILINE,
)


def _runtime_failure(status: str, diagnostic: str) -> RuntimeCatalogObservation:
    return RuntimeCatalogObservation(status=status, diagnostic=diagnostic)


def parse_runtime_prompt_input(
    encoded: str, repo_skills: Path, pack_runtime_root: Path
) -> RuntimeCatalogObservation:
    try:
        payload = json.loads(encoded)
    except (TypeError, ValueError):
        return _runtime_failure("malformed", "CATALOG-RUNTIME-MALFORMED")
    if not isinstance(payload, list):
        return _runtime_failure("malformed", "CATALOG-RUNTIME-MALFORMED")

    skill_blocks: list[str] = []
    for message in payload:
        if not isinstance(message, dict) or not isinstance(message.get("content"), list):
            continue
        for item in message["content"]:
            if (
                isinstance(item, dict)
                and item.get("type") == "input_text"
                and isinstance(item.get("text"), str)
                and "<skills_instructions>" in item["text"]
            ):
                skill_blocks.append(item["text"])
    if len(skill_blocks) != 1:
        return _runtime_failure("malformed", "CATALOG-RUNTIME-MALFORMED")

    skills_text = skill_blocks[0]
    root_matches = list(ROOT_LINE_RE.finditer(skills_text))
    roots = {
        match.group("alias"): Path(match.group("path"))
        for match in root_matches
    }
    if not roots or len(roots) != len(root_matches):
        return _runtime_failure("malformed", "CATALOG-RUNTIME-MALFORMED")

    try:
        expected_pack = _pack_identities(repo_skills)
        pack_runtime_resolved = pack_runtime_root.resolve()
    except (OSError, UnicodeError, ValueError):
        return _runtime_failure("binding-failure", "CATALOG-RUNTIME-BINDING")
    if not expected_pack or not pack_runtime_resolved.is_dir():
        return _runtime_failure("binding-failure", "CATALOG-RUNTIME-BINDING")
    rendered_pack: set[str] = set()
    seen_paths: set[Path] = set()
    shortened_count = 0
    shortened_chars = 0
    total_entries = 0
    entry_matches = list(ENTRY_LINE_RE.finditer(skills_text))
    declared_entry_lines = sum(
        1
        for line in skills_text.splitlines()
        if line.startswith("- ") and " (file: r" in line
    )
    if len(entry_matches) != declared_entry_lines:
        return _runtime_failure("malformed", "CATALOG-RUNTIME-MALFORMED")
    for match in entry_matches:
        root = roots.get(match.group("alias"))
        if root is None:
            return _runtime_failure("binding-failure", "CATALOG-RUNTIME-BINDING")
        relative = Path(match.group("relative"))
        if relative.is_absolute() or ".." in relative.parts:
            return _runtime_failure("binding-failure", "CATALOG-RUNTIME-BINDING")
        root_resolved = root.resolve()
        path = (root_resolved / relative).resolve()
        try:
            path.relative_to(root_resolved)
        except ValueError:
            return _runtime_failure("binding-failure", "CATALOG-RUNTIME-BINDING")
        if path in seen_paths or not path.is_file():
            return _runtime_failure("binding-failure", "CATALOG-RUNTIME-BINDING")
        seen_paths.add(path)
        try:
            name, source_description = _read_name_description(path)
        except (OSError, UnicodeError, ValueError):
            return _runtime_failure("binding-failure", "CATALOG-RUNTIME-BINDING")
        header = match.group("header")
        prompt_description: str | None = None
        plugin_entry = False
        prefix = f"{name}: "
        if header.startswith(prefix):
            prompt_description = header[len(prefix):]
        if prompt_description is None:
            plugin_match = re.match(rf"^[^:]+:{re.escape(name)}: (.*)$", header)
            if plugin_match:
                prompt_description = plugin_match.group(1)
                plugin_entry = True
        if prompt_description is None:
            return _runtime_failure("binding-failure", "CATALOG-RUNTIME-BINDING")
        total_entries += 1
        skill_directory = path.parent.name
        if path.parent.parent == pack_runtime_resolved and skill_directory in expected_pack:
            if plugin_entry or name != expected_pack[skill_directory]:
                return _runtime_failure("binding-failure", "CATALOG-RUNTIME-BINDING")
            rendered_pack.add(skill_directory)
        if prompt_description != source_description:
            shortened_count += 1
            shortened_chars += max(0, len(source_description) - len(prompt_description))

    if total_entries == 0:
        return _runtime_failure("malformed", "CATALOG-RUNTIME-MALFORMED")
    omitted = tuple(sorted(set(expected_pack) - rendered_pack))
    if omitted:
        status = "omitted-pack"
        diagnostic = "CATALOG-PACK-IDENTITY-OMITTED"
    elif shortened_count:
        status = "shortened"
        diagnostic = "CATALOG-DESCRIPTION-SHORTENED"
    else:
        status = "complete"
        diagnostic = "CATALOG-COMPLETE"
    return RuntimeCatalogObservation(
        status=status,
        diagnostic=diagnostic,
        total_entries=total_entries,
        pack_expected=len(expected_pack),
        pack_rendered=len(rendered_pack),
        shortened_count=shortened_count,
        shortened_chars=shortened_chars,
        omitted_pack=omitted,
    )


def observe_runtime_catalog(
    codex_executable: str,
    repo_skills: Path,
    pack_runtime_root: Path,
    *,
    runner=subprocess.run,
    timeout_seconds: float = 20.0,
) -> RuntimeCatalogObservation:
    argv = [codex_executable, "debug", "prompt-input"]
    try:
        completed = runner(
            argv,
            shell=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return _runtime_failure("execution-failure", "CATALOG-RUNTIME-EXECUTION")
    except (OSError, UnicodeError):
        return _runtime_failure("unavailable", "CATALOG-RUNTIME-UNAVAILABLE")
    if completed.returncode != 0:
        return _runtime_failure("execution-failure", "CATALOG-RUNTIME-EXECUTION")
    return parse_runtime_prompt_input(
        completed.stdout, repo_skills, pack_runtime_root
    )


EXTERNAL_GROUPS = ("other-codex-home", "system-builtin", "cross-tool")
ALL_GROUPS = ("pack",) + EXTERNAL_GROUPS


def _pack_names(repo_skills: Path) -> set[str]:
    if not repo_skills.is_dir():
        return set()
    return {
        child.name
        for child in repo_skills.iterdir()
        if child.is_dir() and (child / "SKILL.md").is_file()
    }


def _pack_identities(repo_skills: Path) -> dict[str, str]:
    identities: dict[str, str] = {}
    for directory in sorted(repo_skills.iterdir()):
        skill_md = directory / "SKILL.md"
        if directory.is_dir() and skill_md.is_file():
            name, _description = _read_name_description(skill_md)
            identities[directory.name] = name
    return identities


def discover_entries(
    codex_home: Path, agents_skills_home: Path, repo_skills: Path
) -> list[CatalogEntry]:
    pack_names = _pack_names(repo_skills)
    entries: list[CatalogEntry] = []

    codex_skills_root = codex_home / "skills"
    if codex_skills_root.is_dir():
        for child in sorted(codex_skills_root.iterdir()):
            if not child.is_dir():
                continue
            if child.name == ".system":
                for sub in sorted(child.iterdir()):
                    sub_md = sub / "SKILL.md"
                    if sub.is_dir() and sub_md.is_file():
                        name, desc = _read_name_description(sub_md)
                        entries.append(
                            CatalogEntry(sub.name, "system-builtin", name, desc, sub_md)
                        )
                continue
            skill_md = child / "SKILL.md"
            if skill_md.is_file():
                group = "pack" if child.name in pack_names else "other-codex-home"
                name, desc = _read_name_description(skill_md)
                entries.append(CatalogEntry(child.name, group, name, desc, skill_md))

    if agents_skills_home.is_dir():
        for child in sorted(agents_skills_home.iterdir()):
            skill_md = child / "SKILL.md"
            if child.is_dir() and skill_md.is_file():
                name, desc = _read_name_description(skill_md)
                entries.append(CatalogEntry(child.name, "cross-tool", name, desc, skill_md))

    return entries


def validate(
    entries: list[CatalogEntry],
    context_window: int = REFERENCE_CONTEXT_WINDOW_TOKENS,
    warn_fraction: float = WARN_FRACTION,
    fail_fraction: float = FAIL_FRACTION,
    *,
    enforce: bool = True,
) -> tuple[bool, list[str]]:
    ceiling_chars = round(context_window * CEILING_RATIO)
    totals = {group: 0 for group in ALL_GROUPS}
    counts = {group: 0 for group in ALL_GROUPS}
    for entry in entries:
        totals[entry.group] += entry.cost
        counts[entry.group] += 1

    total_chars = sum(totals.values())
    total_count = sum(counts.values())
    external_chars = sum(totals[g] for g in EXTERNAL_GROUPS)
    external_count = sum(counts[g] for g in EXTERNAL_GROUPS)
    fraction = (total_chars / ceiling_chars) if ceiling_chars else float("inf")

    messages = [
        f"Context window: {context_window} tokens (reference: {REFERENCE_CONTEXT_WINDOW_TOKENS})",
        f"Ceiling: {ceiling_chars} rendered chars (ratio {CEILING_RATIO:.5f} of context window)",
        "",
        f"pack             : {counts['pack']:4d} entries, {totals['pack']:7d} chars (pack-owned, can shrink)",
        f"other-codex-home : {counts['other-codex-home']:4d} entries, {totals['other-codex-home']:7d} chars (not pack-owned)",
        f"system-builtin   : {counts['system-builtin']:4d} entries, {totals['system-builtin']:7d} chars (not pack-owned)",
        f"cross-tool       : {counts['cross-tool']:4d} entries, {totals['cross-tool']:7d} chars (not pack-owned)",
        f"external (sum)   : {external_count:4d} entries, {external_chars:7d} chars",
        "",
        f"Total: {total_count} entries, {total_chars} rendered chars",
        f"Fraction of ceiling: {fraction * 100:.2f}%  (warn >= {warn_fraction * 100:.0f}%, fail >= {fail_fraction * 100:.0f}%)",
    ]

    ok = True
    if fraction >= fail_fraction and enforce:
        ok = False
        messages.append(
            f"FAIL: rendered catalog is {fraction * 100:.2f}% of ceiling "
            f"({total_chars}/{ceiling_chars} chars) >= fail threshold {fail_fraction * 100:.0f}%. "
            "Trim, shorten, split, or deduplicate the pack's OWN skill descriptions "
            "(the 'pack' group above) until the total fraction drops back under the warn band. "
            "The other-codex-home/system-builtin/cross-tool groups cannot be shrunk by this "
            "pack, but they consume the same shared budget -- if they dominate the growth, "
            "the pack must still claw back headroom on its own side of the ledger."
        )
    elif fraction >= fail_fraction:
        messages.append(
            f"ESTIMATE: rendered catalog is {fraction * 100:.2f}% of ceiling "
            f"({total_chars}/{ceiling_chars} chars); the direct runtime observation "
            "owns the final verdict for this installed catalog."
        )
    elif fraction >= warn_fraction:
        messages.append(
            f"WARNING: rendered catalog is {fraction * 100:.2f}% of ceiling "
            f"({total_chars}/{ceiling_chars} chars), in the warn band "
            f"[{warn_fraction * 100:.0f}%, {fail_fraction * 100:.0f}%). No action required to keep "
            "shipping, but avoid adding more skill entries without also trimming existing "
            "descriptions."
        )
    else:
        messages.append(
            f"PASS: rendered catalog is {fraction * 100:.2f}% of ceiling, below warn threshold "
            f"{warn_fraction * 100:.0f}%."
        )

    return ok, messages


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--codex-home",
        type=Path,
        default=Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))),
        help="Codex home directory whose skills/ subdirectory holds the installed catalog "
        "(default: $CODEX_HOME or ~/.codex).",
    )
    parser.add_argument(
        "--agents-skills-home",
        type=Path,
        default=Path.home() / ".agents" / "skills",
        help="Cross-tool skills alias root (default: ~/.agents/skills).",
    )
    parser.add_argument(
        "--repo-skills",
        type=Path,
        default=DEFAULT_REPO_SKILLS,
        help="This repository's own Codex skill source tree, used to attribute ownership "
        "(default: src.codex/skills).",
    )
    parser.add_argument(
        "--context-window",
        type=int,
        default=REFERENCE_CONTEXT_WINDOW_TOKENS,
        help=f"Model context window in tokens (default: {REFERENCE_CONTEXT_WINDOW_TOKENS}, "
        "the observed default across every current model profile in the installed runtime).",
    )
    parser.add_argument("--warn-fraction", type=float, default=WARN_FRACTION)
    parser.add_argument("--fail-fraction", type=float, default=FAIL_FRACTION)
    args = parser.parse_args(argv)

    print(f"=== Codex skill catalog budget validation ===")
    print(f"CODEX_HOME: {args.codex_home}")
    print(f"agents-skills-home: {args.agents_skills_home}")
    print(f"repo-skills (ownership reference): {args.repo_skills}")

    if not args.repo_skills.is_dir():
        print(f"FAIL: repo-skills ownership reference not found: {args.repo_skills}")
        print("RESULT: FAIL")
        return 1

    codex_skills_root = args.codex_home / "skills"
    if not codex_skills_root.is_dir():
        print(f"SKIP: no installed Codex skills catalog found at {codex_skills_root}")
        print("RESULT: SKIP")
        return 0

    entries = discover_entries(args.codex_home, args.agents_skills_home, args.repo_skills)
    default_codex_home = Path(
        os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
    )
    default_agents_home = Path.home() / ".agents" / "skills"
    runtime_target = (
        args.codex_home.resolve() == default_codex_home.resolve()
        and args.agents_skills_home.resolve() == default_agents_home.resolve()
        and args.repo_skills.resolve() == DEFAULT_REPO_SKILLS.resolve()
        and args.context_window == REFERENCE_CONTEXT_WINDOW_TOKENS
        and args.warn_fraction == WARN_FRACTION
        and args.fail_fraction == FAIL_FRACTION
    )
    ok, messages = validate(
        entries,
        context_window=args.context_window,
        warn_fraction=args.warn_fraction,
        fail_fraction=args.fail_fraction,
        enforce=not runtime_target,
    )
    if runtime_target:
        executable = shutil.which("codex")
        observation = (
            observe_runtime_catalog(executable, args.repo_skills, codex_skills_root)
            if executable
            else _runtime_failure("unavailable", "CATALOG-RUNTIME-UNAVAILABLE")
        )
        messages.extend(
            (
                "",
                f"Runtime catalog: status={observation.status}, "
                f"entries={observation.total_entries}, "
                f"pack={observation.pack_rendered}/{observation.pack_expected}, "
                f"shortened={observation.shortened_count}, "
                f"removed-chars={observation.shortened_chars}",
            )
        )
        if observation.status == "complete":
            ok = True
            messages.append(
                "PASS: CATALOG-COMPLETE; the authoritative model-visible catalog "
                "contains every expected pack identity with complete descriptions."
            )
        elif observation.status == "shortened":
            ok = True
            messages.append(
                "WARNING: CATALOG-DESCRIPTION-SHORTENED; the authoritative "
                "model-visible catalog retains every expected pack identity but "
                f"shortens {observation.shortened_count} descriptions by "
                f"{observation.shortened_chars} characters."
            )
        elif observation.status == "omitted-pack":
            ok = False
            messages.append(
                "FAIL: CATALOG-PACK-IDENTITY-OMITTED; missing expected pack skills: "
                + ", ".join(observation.omitted_pack)
            )
        else:
            ok = False
            messages.append(
                f"FAIL: {observation.diagnostic}; authoritative Codex runtime "
                "catalog evidence is unavailable or invalid."
            )
    for message in messages:
        print(message)
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
