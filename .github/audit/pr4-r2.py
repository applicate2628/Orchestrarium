from __future__ import annotations

import hashlib
import os
import re
import runpy
from pathlib import Path

ROOT = Path.cwd()
SOURCE_HEAD = "3dbfb9faf824365f5898fe52dd10093f4d75da9c"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8", newline="\n")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"{path}: expected one exact preimage, found {count}: {old[:120]!r}"
        )
    write(path, text.replace(old, new, 1))


# Static audit: postponed annotations still need names to exist for lint/type tooling.
replace_once(
    "scripts/production_installer.py",
    "from typing import Any\n",
    "from typing import Any, Callable\n",
)

# Hook-health: an injected inventory provider is the whole host boundary for tests and
# adapters. Resolve the Codex executable only inside the real host probe.
replace_once(
    "scripts/check-hook-health.py",
    """def _codex_hooks_list(
    *,
    codex_command: list[str],
    codex_home: Path,
    query_cwd: Path,
    timeout: float = 15,
) -> list[dict[str, Any]]:
    \"\"\"Ask the Codex host for its current hook admission inventory, read-only.\"\"\"
    if not codex_command or not Path(codex_command[0]).is_absolute():
""",
    """def _codex_hooks_list(
    *,
    codex_command: list[str] | None,
    codex_home: Path,
    query_cwd: Path,
    timeout: float = 15,
) -> list[dict[str, Any]]:
    \"\"\"Ask the Codex host for its current hook admission inventory, read-only.\"\"\"
    if codex_command is None:
        codex_command = resolve_codex_command(os.environ.get(\"CODEX_BIN\"))
    if not codex_command or not Path(codex_command[0]).is_absolute():
""",
)
replace_once(
    "scripts/check-hook-health.py",
    """    touched_identities: set[str],
    codex_command: list[str],
    codex_home: Path,
""",
    """    touched_identities: set[str],
    codex_command: list[str] | None,
    codex_home: Path,
""",
)
replace_once(
    "scripts/check-hook-health.py",
    """                codex_command=codex_command
                or resolve_codex_command(os.environ.get(\"CODEX_BIN\")),
""",
    """                codex_command=codex_command,
""",
)

hook_test = "tests/test_hook_health.py"
text = read(hook_test)
anchor = '    monkeypatch.setattr(CHECKER, "_codex_hooks_list", lambda **_kwargs: records)\n'
function_start = text.index("def test_hook_health_report_allows_only_touched_pending(")
function_end = text.index("\n\ndef _host_trust_fixture", function_start)
block = text[function_start:function_end]
if block.count(anchor) != 1:
    raise SystemExit("test_hook_health.py: injected inventory anchor mismatch")
regression = (
    anchor
    + "\n"
    + "    def unexpected_codex_resolution(_value: str | None = None) -> list[str]:\n"
    + "        raise AssertionError(\"injected inventory must not resolve Codex\")\n"
    + "\n"
    + '    monkeypatch.setattr(CHECKER, "resolve_codex_command", unexpected_codex_resolution)\n'
)
block = block.replace(anchor, regression, 1)
write(hook_test, text[:function_start] + block + text[function_end:])

# SessionStart reminder tests intentionally keep an independent, static oracle. Refresh
# that oracle from the reviewed canonical policy rather than importing it at test time.
policy = runpy.run_path("scripts/universal-hooks/scripts/mcp_continuity_policy.py")
session_context = policy["SESSION_START_CONTEXT"]
turn_context = policy["TURN_ANCHOR_CONTEXT"]
stateful = next(
    line
    for line in session_context.splitlines()
    if line.startswith("For any stateful or indexed repository-understanding tool")
)
turn_marker = "Repository-understanding freshness:"
turn_freshness = turn_context[turn_context.index(turn_marker) :]

reminder_test = "tests/test_sessionstart_reminder_python_hooks.py"
text = read(reminder_test)
start = text.index("STATEFUL_REPOSITORY_TOOL_CONTEXT = (")
end = text.index("# (script, config subdir under cwd", start)
text = (
    text[:start]
    + f"STATEFUL_REPOSITORY_TOOL_CONTEXT = {stateful!r}\n\n"
    + f"TURN_ANCHOR_FRESHNESS_CONTEXT = {turn_freshness!r}\n\n"
    + text[end:]
)
start = text.index('MCP_CONTEXT = "\\n".join((')
end = text.index("DELEGATION_HEADING =", start)
rendered_lines = "".join(f"    {line!r},\n" for line in session_context.splitlines())
text = text[:start] + f'MCP_CONTEXT = "\\n".join((\n{rendered_lines}))\n\n' + text[end:]
write(reminder_test, text)

# Correct the Russian mirror to the real structured stdout/exit-zero advisory contract.
ru_path = "references-claude/ru/claude-md-structural-enforcement.md"
replace_once(
    ru_path,
    "Он пишет UTF-8 stderr-предупреждение, ВСЕГДА разрешает вызов инструмента и fail-open; при попадании он теперь выходит с кодом 1 (никогда 2, что заблокировало бы), а чистая проверка выходит с кодом 0 — тот же контракт видимости, что и у его четырёх соседних аудитов, поэтому его предупреждение всплывает как неблокирующее уведомление в транскрипте, а не остаётся невидимым в debug log.",
    "Он доставляет предупреждение МОДЕЛИ через `hookSpecificOutput.additionalContext` в stdout, ВСЕГДА разрешает вызов инструмента и работает fail-open; и при попадании, и при чистой проверке выходит с кодом 0 (никогда 2, который заблокировал бы вызов) — тот же контракт доставки, что и у его четырёх соседних аудитов, поэтому предупреждение поступает непосредственно модели, а не остаётся только уведомлением транскрипта или debug log.",
)
replace_once(
    ru_path,
    "При попадании он пишет одну строку stderr `[typed-routing AUDIT]`, указывающую на типизированный реестр (`.claude/agents/*.md` — напр. toolchain-engineer / platform-engineer для `.ps1`/install-работы, engineer-роль для кода, reviewer-роль для review) и выходит с кодом 1 (никогда 2), поэтому подсказка видима, а не только в debug log; чистая проверка выходит с кодом 0.",
    "При попадании он доставляет одно сообщение `[typed-routing AUDIT]` МОДЕЛИ через `hookSpecificOutput.additionalContext` в stdout, указывающее на типизированный реестр (`.claude/agents/*.md` — напр. toolchain-engineer / platform-engineer для `.ps1`/install-работы, engineer-роль для кода, reviewer-роль для review), и выходит с кодом 0 (никогда 2), поэтому подсказка видима модели и не блокирует вызов; чистая проверка также выходит с кодом 0.",
)
validator_namespace = runpy.run_path("scripts/validate-claude-md.py")
raw = (ROOT / ru_path).read_bytes()
_ids, payloads = validator_namespace["_payload_inventory"](raw)
if payloads is None:
    raise SystemExit("Russian mirror payload inventory became invalid")
payload = payloads["hook-behavior-contracts"]
payload_size = len(payload)
payload_sha = hashlib.sha256(payload).hexdigest()
validator_path = "scripts/validate-claude-md.py"
text = read(validator_path)
pin_pattern = re.compile(
    r"RU_HOOK_BEHAVIOR_PAYLOAD_PIN = \(\n"
    r"\s+[0-9_]+,\n"
    r'\s+"[0-9a-f]{64}",\n'
    r"\)"
)
pin_replacement = (
    "RU_HOOK_BEHAVIOR_PAYLOAD_PIN = (\n"
    f"    {payload_size:_},\n"
    f'    "{payload_sha}",\n'
    ")"
)
text, count = pin_pattern.subn(pin_replacement, text, count=1)
if count != 1:
    raise SystemExit("validate-claude-md.py: Russian payload pin anchor mismatch")
write(validator_path, text)
print(f"Russian hook payload pin: {payload_size} {payload_sha}")

# Exact SHA-256 contracts require host-independent checkout bytes. The later -text
# fixture rule remains more specific and preserves historical CRLF payloads.
attributes_path = ".gitattributes"
text = read(attributes_path)
attributes_anchor = (
    "# Historical accepted-prior payloads preserve their source blob bytes, including CRLF.\n"
)
lf_block = (
    "# Source, test, manifest, and human-contract files participate in exact\n"
    "# SHA-256 byte pins. Keep their checkout bytes host-independent.\n"
    ".gitattributes text eol=lf\n"
    "*.py text eol=lf\n"
    "*.json text eol=lf\n"
    "*.jsonl text eol=lf\n"
    "*.md text eol=lf\n"
    "*.toml text eol=lf\n"
    "*.yaml text eol=lf\n"
    "*.yml text eol=lf\n"
    "*.sh text eol=lf\n"
    "*.ps1 text eol=lf\n\n"
)
if text.count(attributes_anchor) != 1 or "*.py text eol=lf" in text:
    raise SystemExit(".gitattributes LF-policy anchor mismatch")
write(attributes_path, text.replace(attributes_anchor, lf_block + attributes_anchor, 1))

eol_test = ROOT / "tests/test_text_eol_contract.py"
if eol_test.exists():
    raise SystemExit("tests/test_text_eol_contract.py already exists")
eol_test.write_text(
    '''"""Repository byte pins must survive checkout on every supported host."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ATTRIBUTES = ROOT / ".gitattributes"
REQUIRED_RULES = (
    ".gitattributes text eol=lf",
    "*.py text eol=lf",
    "*.json text eol=lf",
    "*.jsonl text eol=lf",
    "*.md text eol=lf",
    "*.toml text eol=lf",
    "*.yaml text eol=lf",
    "*.yml text eol=lf",
    "*.sh text eol=lf",
    "*.ps1 text eol=lf",
)
REPRESENTATIVES = (
    "scripts/production_installer.py",
    "shared/agents-mode.presets.json",
    "references-claude/ru/claude-md-structural-enforcement.md",
    "src.codex/skills/github-pr-review-bot/SKILL.md",
)
HISTORICAL_FIXTURE = "tests/fixtures/canonical-skill-priors/codex/example/SKILL.md"


def _attributes(path: str) -> dict[str, str]:
    result = subprocess.run(
        ["git", "check-attr", "text", "eol", "--", path],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    parsed: dict[str, str] = {}
    for row in result.stdout.splitlines():
        _path, attribute, value = row.rsplit(": ", 2)
        parsed[attribute] = value
    return parsed


def test_byte_pinned_text_families_are_explicitly_lf() -> None:
    lines = ATTRIBUTES.read_text(encoding="utf-8").splitlines()
    for rule in REQUIRED_RULES:
        assert lines.count(rule) == 1
    fixture_rule = "tests/fixtures/canonical-skill-priors/*/*/** -text"
    assert lines.count(fixture_rule) == 1
    assert lines.index(fixture_rule) > max(lines.index(rule) for rule in REQUIRED_RULES)

    for relative in REPRESENTATIVES:
        assert _attributes(relative) == {"text": "set", "eol": "lf"}
        assert b"\r\n" not in (ROOT / relative).read_bytes()

    assert _attributes(HISTORICAL_FIXTURE)["text"] == "unset"
''',
    encoding="utf-8",
    newline="\n",
)

# Repair the inherited cross-host test harness without weakening production. On POSIX,
# a tiny driver substitutes a regular fake .exe path into sys.executable before main()
# resolves the registration target; the fake file is validated but never executed.
install_test = "tests/test_install_hypothesis_hook.py"
text = read(install_test)
helper_anchor = "\n\ndef run_installer(\n"
helper = r'''


def _test_python_executable(host_os: str) -> Path:
    if host_os != "windows" or os.name == "nt":
        return Path(sys.executable)
    executable = Path(tempfile.gettempdir()) / (
        f"orchestrarium-test-python-{os.getpid()}.exe"
    )
    if not executable.exists():
        executable.write_bytes(b"MZ-test-only")
    return executable.absolute()


def _installer_command_prefix(host_os: str) -> list[str]:
    if host_os != "windows" or os.name == "nt":
        return [sys.executable, str(HOOK_INSTALLER)]
    driver = (
        "import runpy,sys;"
        "fake,script,*forwarded=sys.argv[1:];"
        "sys.executable=fake;"
        "sys.argv=[script,*forwarded];"
        "runpy.run_path(script,run_name='__main__')"
    )
    return [
        sys.executable,
        "-c",
        driver,
        str(_test_python_executable("windows")),
        str(HOOK_INSTALLER),
    ]


def _assert_registered_python(
    case: unittest.TestCase, value: str, host_os: str = "posix"
) -> None:
    case.assertEqual(Path(value), _test_python_executable(host_os))
'''
if text.count(helper_anchor) != 1 or "def _test_python_executable" in text:
    raise SystemExit("test_install_hypothesis_hook.py: helper anchor mismatch")
text = text.replace(helper_anchor, helper + helper_anchor, 1)
old_prefix = "    cmd = [\n        sys.executable,\n        str(HOOK_INSTALLER),\n"
new_prefix = "    cmd = [\n        *_installer_command_prefix(host_os),\n"
if text.count(old_prefix) != 1:
    raise SystemExit("test_install_hypothesis_hook.py: CLI prefix anchor mismatch")
text = text.replace(old_prefix, new_prefix, 1)

resolved_assertion = re.compile(
    r'self\.assertEqual\(Path\((?P<value>(?:hook|our_hook)\["command"\])\), '
    r'Path\(sys\.executable\)\.resolve\(\)\)'
)
text, assertion_count = resolved_assertion.subn(
    lambda match: f'_assert_registered_python(self, {match.group("value")})', text
)
if assertion_count < 6:
    raise SystemExit(
        f"test_install_hypothesis_hook.py: expected >=6 executable assertions, found {assertion_count}"
    )

windows_function = text.index(
    "    def test_install_claude_windows_python_exec_form(self) -> None:"
)
windows_function_end = text.index("\n    def ", windows_function + 8)
block = text[windows_function:windows_function_end]
old_assertion = '_assert_registered_python(self, hook["command"])'
if block.count(old_assertion) != 1:
    raise SystemExit("Windows Claude executable assertion anchor mismatch")
block = block.replace(
    old_assertion,
    '_assert_registered_python(self, hook["command"], "windows")',
    1,
)
text = text[:windows_function] + block + text[windows_function_end:]

# Calls inside host_os loops.
loop_pattern = re.compile(
    r"(?P<prefix>\n\s+host_os,\n\s+platform,\n\s+)python_executable=sys\.executable,"
)
text, loop_count = loop_pattern.subn(
    lambda match: match.group("prefix")
    + 'python_executable=str(_test_python_executable(host_os)),',
    text,
)
if loop_count != 2:
    raise SystemExit(f"expected two host_os-loop executable seams, found {loop_count}")

# Direct literal-Windows calls.
literal_pattern = re.compile(
    r'(?P<prefix>\n\s+"windows",\n\s+"(?:claude|codex)",\n\s+)'
    r"python_executable=sys\.executable,"
)
text, literal_count = literal_pattern.subn(
    lambda match: match.group("prefix")
    + 'python_executable=str(_test_python_executable("windows")),',
    text,
)
if literal_count < 3:
    raise SystemExit(f"expected >=3 literal Windows executable seams, found {literal_count}")
if "python_executable=sys.executable" in text:
    raise SystemExit("unconverted cross-host python_executable remains")

old_name_check = "Path(sys.executable).name.casefold()"
if text.count(old_name_check) != 1:
    raise SystemExit("Windows executable name assertion anchor mismatch")
text = text.replace(
    old_name_check, '_test_python_executable("windows").name.casefold()', 1
)
old_expected = 'f"{PureWindowsPath(sys.executable).as_posix()} "'
if text.count(old_expected) != 1:
    raise SystemExit("Windows command expected-path anchor mismatch")
text = text.replace(
    old_expected,
    'f"{PureWindowsPath(_test_python_executable(\"windows\")).as_posix()} "',
    1,
)
write(install_test, text)

# Document only operator-visible changes introduced by this audit.
notes_path = "RELEASE_NOTES.md"
text = read(notes_path)
heading = "## 2026-09-04\n\n"
bullets = (
    "- **Byte-pinned source, test, manifest, and human-contract files now checkout with Line Feed (LF) endings on every host.** Python, JavaScript Object Notation (JSON), JSON Lines, Markdown, Tom's Obvious Minimal Language (TOML), YAML Ain't Markup Language (YAML), shell, and PowerShell families are explicitly `eol=lf`, while accepted-prior fixture payloads retain their historical bytes through the later `-text` exception. **Why it matters:** Windows checkout conversion can no longer invalidate Secure Hash Algorithm 256-bit (SHA-256) pins or make an unchanged installer or projection appear corrupt.\n"
    "- **Deep-audit test and mirror contracts now match shipped runtime behavior.** Hook-health resolves the Codex executable only inside the real host probe, the SessionStart oracle reflects generic runtime discovery, the Russian Claude reference documents structured stdout advisory delivery with exit zero, and cross-host installer tests no longer pass a Portable Operating System Interface (POSIX) shim as a Windows executable. **Why it matters:** injected inventory tests, translated operator guidance, and Linux/Windows verification no longer fail or mislead for reasons unrelated to production behavior.\n"
)
if text.count(heading) != 1 or bullets.splitlines()[0] in text:
    raise SystemExit("RELEASE_NOTES.md audit bullet anchor mismatch")
write(notes_path, text.replace(heading, heading + bullets + "\n", 1))

print("deep-audit r2 patch applied")
