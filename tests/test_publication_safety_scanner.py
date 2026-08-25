"""Regression tests for the allowlist-aware publication leak-scanner.

Drives the REAL scanner (`check-publication-safety.py`, both the Claude and
Codex byte-identical-logic copies) via its production `--cached` staged-scan
mode against a throwaway git repo, asserting EXIT CODES (the scanner contract:
exit 1 = BLOCK a leak marker was found; exit 0 = PASS clean). Exit-code
assertions are robust to multi-pattern double-fire (MF7).

Coverage:
  - must-BLOCK rows: concrete Windows/MSYS/macOS user homes (incl. lowercase
    drive, forward-slash, the MSYS-dead leading-slash forms), dev/work/projects
    roots, exact-vs-substring example tokens (`username2`, `meadow`), every
    non-path secret/transcript marker, and secret-combined-with-allowed-token
    lines (MF3).
  - must-PASS rows: every placeholder form, all 8 ALLOWED_USER_TOKENS,
    `%USERPROFILE%` / `%USERNAME%` / `$HOME` / `${...}`, `C:\\Windows\\...`,
    `C:\\Program Files\\...`, and generic prose.
  - Wave A audit pins: Anthropic credential-material content rows (synthetic
    token, env-key assignment) BLOCK while a prose prefix mention PASSes; the
    credential FILENAME blocks in every casing; and the scanner's own source
    passes only under its own filename (self-exemption keyed, no general hole).
  - F7 pins (2026-07-27, delimiter-class over-breadth): a private-field
    assignment, a private call, a secrets-mount path value, a documentation
    placeholder, and an underscored C# DI member access all PASS -- none
    contains a secret, and all five measured BLOCKING against the
    un-narrowed `[^[:alnum:][:space:]]` delimiter class before this fix.

MF6 (gate safety): this test file is itself scanned by the publication gate, so
it must contain NO machine-local-path literal that the scanner would flag. Every
flaggable path is therefore ASSEMBLED AT RUNTIME from fragments (drive letter,
separator, root word, and segment kept as separate string pieces joined by
`_join`), so no complete flaggable path token ever appears as a literal in the
tracked source. A self-test (`test_this_test_file_is_gate_safe`) imports the
reference `find_machine_paths` and asserts this file has zero flaggable lines.
"""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import importlib.util
import hashlib
import inspect
import io
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_SCANNER = REPO_ROOT / "scripts" / "universal-hooks" / "scripts" / "check-publication-safety.py"
CODEX_SCANNER = REPO_ROOT / "src.codex" / "skills" / "lead" / "scripts" / "check-publication-safety.py"
CLAUDE_SCANNER = REPO_ROOT / "src.claude" / "agents" / "scripts" / "check-publication-safety.py"
CODEX_REF = REPO_ROOT / "src.codex" / "skills" / "lead" / "hooks" / "check-machine-local-path.py"
SCANNERS = (CODEX_SCANNER, CLAUDE_SCANNER)

BACKSLASH = chr(92)  # keep the literal backslash out of source path literals


def _join(*parts: str) -> str:
    """Concatenate fragments with no separator. Used so a complete flaggable
    path is only ever built at runtime, never present as a source literal."""
    return "".join(parts)


def _git() -> str | None:
    from shutil import which
    return which("git")


def _assert_batch_finding_lines(
    test: unittest.TestCase,
    output: str,
    rows: dict[str, str],
) -> None:
    """Every named blocking fixture must produce a finding on its fixture line."""
    for line, name in enumerate(rows, start=1):
        with test.subTest(row=name, line=line):
            test.assertRegex(output, rf"\bline={line}\b class=", f"{name!r} must report its fixture line")


def _load_find_machine_paths():
    spec = importlib.util.spec_from_file_location("_mlp_ref_test", str(CODEX_REF))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.find_machine_paths


def _load_canonical_scanner(name: str):
    spec = importlib.util.spec_from_file_location(name, str(CANONICAL_SCANNER))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop(name, None)
    return mod


# --- Row builders (assembled at runtime; no flaggable literal in source) ------
# Each entry is the file CONTENT to stage. Drive letters / separators / root
# words / segments are kept as fragments and joined so the tracked test source
# never contains a complete machine-local path token.

WIN = "C" + ":"            # "C:" assembled
WIN_D = "D" + ":"
WIN_LOWER = "c" + ":"
BS = BACKSLASH
FS = "/"
USERS = "Use" + "rs"       # "Users" split so the source has no `:\\Users` literal
users_lower = "use" + "rs"
REAL = "real" + "user"     # a concrete (non-allowed) username
DEV = "de" + "v"
WORK = "wo" + "rk"
PROJ = "proj" + "ects"
HOME = "ho" + "me"
ELL = chr(0x2026)          # "…" U+2026, kept out of source as pure-ASCII chr()


def block_rows() -> dict[str, str]:
    return {
        "b01_win_home": _join(WIN, BS, USERS, BS, REAL),
        "b02_win_home_deep": _join(WIN, BS, USERS, BS, REAL, BS, ".claude", BS, "agents"),
        "b03_win_home_lower": _join(WIN_LOWER, BS, users_lower, BS, "petya"),
        "b04_win_home_fwd": _join(WIN, FS, USERS, FS, REAL),
        "b05_dev_root": _join(WIN_D, BS, DEV, BS, "SomeOrg", BS, "SomeProj"),
        "b06_work_root": _join(WIN_D, BS, WORK, BS, "proj"),
        "b07_projects_root": _join(WIN, BS, PROJ, BS, "petya"),  # realistic name (see adjacent finding re: \x)
        "b08_posix_home": _join(FS, HOME, FS, "petya", FS, WORK),
        "b09_macos_home": _join(FS, USERS, FS, "petya", FS, "proj"),
        "b10_msys_home": _join(FS, "c", FS, USERS, FS, "petya", FS, "x"),
        "b11_msys_dev": _join(FS, "d", FS, DEV, FS, "SomeOrg"),
        "b12_token_substring_username2": _join(WIN, BS, USERS, BS, "username2"),
        "b13_token_substring_meadow": _join(WIN, BS, USERS, BS, "meadow"),
        # non-path secrets / transcript markers (assembled so no real secret literal sits in source)
        "b14_aws": "AKIA" + ("A" * 16),
        "b15_ghp": "ghp_" + ("a" * 36),
        "b16_password": "pass" + "word" + ": hunter2",
        "b17_bearer": "Bea" + "rer abc.def.ghi",
        "b18_timestamp": "[" + "12:34:56" + "] transcript line",
        "b19_human": "Hum" + "an: hello there",
        "b20_repl": ">>" + "> repl prompt",
        # MF3: a secret on a line that ALSO contains an allowed path token must STILL block.
        "b21_secret_plus_allowed": _join("pass", "word", ": hunter2  ", WIN, BS, USERS, BS, "<you>"),
        "b22_aws_plus_token": _join("AKIA", "A" * 16, " near ", WIN, BS, USERS, BS, "you"),
        # NEW (Change B): UNC host/share user homes -> concrete machine-local leak.
        "b23_unc_host": _join(BS, BS, "host", BS, USERS, BS, REAL),
        "b24_unc_share": _join(BS, BS, "srv", BS, "share", BS, USERS, BS, REAL),
        "b25_unc_deep_share": _join(BS, BS, "srv", BS, "share", BS, "sub", BS, USERS, BS, REAL),
        # NEW (Wave A audit): Anthropic credential-material content patterns
        # (assembled per MF6 so no trippable token literal sits in this source).
        "b26_sk_ant_token": _join("sk-", "ant-", "a" * 20),
        "b27_anthropic_key_assignment": _join("ANTHROPIC_", "API_", "KEY", "=", "x" * 8),
        # NEW (2026-07-26 value-shape fix): a real secret VALUE for each of the
        # 4 reworked patterns (password/secret/token/api-key) must still BLOCK
        # under the new anchor + value-shape requirement -- these are the
        # POSITIVE-direction fixtures the fix contract requires alongside the
        # negative (declaration) rows in pass_rows() below. Assembled per MF6
        # so no complete trigger literal sits contiguously in this source.
        "b28_secret_quoted_leak": _join("sec", "ret", " = ", '"', "a1b2c3d4e5f6g7h8ijk", '"'),
        "b29_token_quoted_leak": _join("to", "ken", " = ", '"', "a1b2c3d4e5f6g7h8ijk", '"'),
        "b30_apikey_quoted_leak": _join("api", "Key", " = ", '"', "AbCdEf123456ghijklmn", '"'),
        "b31_apikey_bare_digit_leak": _join("api", "_key", "=", "a1b2c3d4e5f6"),
        # Anchor-widening positive guard: a snake_case / camelCase / ALL-CAPS
        # identifier segment must still BLOCK with a real leak value present.
        # b34 also pins the case-sensitivity widening: the old `[Tt]oken`
        # never matched all-caps TOKEN at all (verified pre-fix, see the
        # implementer report), so this row is a coverage IMPROVEMENT, not
        # just a regression guard.
        "b32_access_token_snake_leak": _join("access", "_to", "ken", " = ", '"', "a1b2c3d4e5f6g7h8ijk", '"'),
        "b33_apiToken_camel_leak": _join("api", "To", "ken", " = ", '"', "a1b2c3d4e5f6g7h8ijk", '"'),
        "b34_AUTH_TOKEN_upper_leak": _join("AUTH", "_TO", "KEN", " = ", '"', "A1B2C3D4E5F6G7H8IJK", '"'),
        # NEW (2026-07-27 F1 fix): a quote-STYLE regression reproduced by
        # $security-reviewer -- the quoted branch used to match a literal `"`
        # only, so a SINGLE-quoted or BACKTICK-quoted leak of any length or
        # digit content passed clean (neither `'` nor `` ` `` is in the bare
        # alphabet either). This is the exact false-negative direction this
        # work item exists to close; single-quoted strings are Python's own
        # idiomatic style, and Python is this repo's hook language. Assembled
        # per MF6 so no complete trigger literal sits contiguously in source.
        "b35_token_single_quoted_leak": _join("to", "ken", " = ", "'", "a1b2c3d4e5f6g7h8ijkl", "'"),
        "b36_token_single_quoted_colon_leak": _join("to", "ken", ": ", "'", "a1b2c3d4e5f6g7h8ijkl", "'"),
        "b37_token_backtick_leak": _join("to", "ken", " = ", "`", "a1b2c3d4e5f6g7h8ijkl", "`"),
        "b38_password_single_quoted_leak": _join("pass", "word", " = ", "'", "a1b2c3d4e5f6g7h8ijkl", "'"),
        # NEW (2026-07-27 F2 fix): a quoted value below the flat 12-char floor
        # but WITH a digit used to pass clean even though the identical BARE
        # value blocks (quoting a real secret made it disappear). Fixed by
        # applying the same 5-chars-one-side-of-a-digit bare shape inside the
        # quote/delimiter too. `Summ3r2024` is the reviewer's own example.
        "b39_password_quoted_short_digit_leak": _join("pass", "word", " = ", '"', "Summ3r2024", '"'),
        "b40_token_quoted_short_digit_leak": _join("to", "ken", " = ", '"', "short123", '"'),
        # F4 regression pin: the effective bare floor is 10 chars (not the 6-char
        # nominal floor) when the digit sits centered, because the digit must
        # fall with >=5 chars on ONE side. `abcd5efghi` (10 chars, 4-and-5 split
        # around the digit) is the shortest centered-digit value that still
        # blocks; see the matching pass_rows() pin for the 9-char value that
        # stays clean. Assembled per MF6.
        "b41_token_centered_digit_floor_ten": _join("to", "ken", " = ", "abcd5efghi"),
    }


def pass_rows() -> dict[str, str]:
    return {
        "p01_angle_name": _join(WIN, BS, USERS, BS, "<name>"),
        "p02_angle_you": _join(WIN, BS, USERS, BS, "<you>"),
        "p03_ellipsis": _join(WIN, BS, USERS, BS, "..."),
        "p04_token_you": _join(WIN, BS, USERS, BS, "you"),
        "p05_token_user": _join(WIN, BS, USERS, BS, "user"),
        "p06_token_username": _join(WIN, BS, USERS, BS, "username"),
        "p07_token_name": _join(WIN, BS, USERS, BS, "name"),
        "p08_token_test": _join(WIN, BS, USERS, BS, "test"),
        "p09_token_example": _join(WIN, BS, USERS, BS, "example"),
        "p10_token_me": _join(WIN, BS, USERS, BS, "me"),
        "p11_token_x": _join(WIN, BS, USERS, BS, "x"),
        "p12_userprofile": "%USER" + "PROFILE%",
        "p13_username_var": _join(WIN, BS, USERS, BS, "%USER" + "NAME%"),
        "p14_home_var": "$" + "HOME",
        "p15_brace_var": "$" + "{CLAUDE_PROJECT_DIR}",
        "p16_user_brace_var": _join(WIN, FS, USERS, FS, "$" + "{USER}"),
        "p17_windows_dir": _join(WIN, BS, "Windows", BS, "System32", BS, "drivers"),
        "p18_program_files": _join(WIN, BS, "Program Files", BS, "App"),
        "p19_prose": "This prose mentions Users and home directories generically.",
        # NEW (Change B): UNC placeholder + allowed token must PASS.
        "p20_unc_angle_you": _join(BS, BS, "host", BS, USERS, BS, "<you>"),
        "p21_unc_token_you": _join(BS, BS, "host", BS, USERS, BS, "you"),
        "p22_unc_ellipsis_doc": _join(BS, BS, "host", BS, USERS, BS, "..."),
        # NEW (Change A): U+2026 ellipsis placeholder in every form must PASS.
        "p23_u2026_backslash": _join(WIN, BS, USERS, BS, ELL),
        "p24_u2026_forward": _join(WIN, FS, USERS, FS, ELL),
        "p25_u2026_macos": _join(FS, USERS, FS, ELL),
        "p26_u2026_bare": _join("see ", ELL, " here"),
        "p27_mixed_dot_ellipsis": _join(WIN, FS, USERS, FS, ".", ELL, "."),
        "p28_u2026_unc": _join(BS, BS, "host", BS, USERS, BS, ELL),
        # SELF-FLOOD GUARDS (C5): an ESCAPED Windows-path JSON literal and a
        # UNC-with-"..." doc literal must BOTH stay exit-0 (the left-anchor +
        # host-label guard rejects the drive-prefixed \\Users\\, the ellipsis
        # filter clears the "..." segment). These are the exact shapes that the
        # commit ADDING these rows would otherwise self-trip the scanner with.
        "p29_json_escaped_literal": _join('"', WIN, BS, BS, USERS, BS, BS, "test", '"'),
        "p30_unc_doc_ellipsis_literal": _join(BS, BS, "host", BS, USERS, BS, "..."),
        # NEW (Wave A audit): a PROSE mention of the credential-token prefixes
        # (no actual token value, no assignment) must stay publishable.
        "p31_credential_prefix_prose": _join(
            "docs discuss the sk-", "ant- token prefix and the ANTHROPIC_",
            " env prefix without any concrete value",
        ),
        # NEW (2026-07-26 value-shape fix): the exact false-positive
        # reproduction -- C# parameter/field DECLARATIONS with no secret
        # present -- must PASS under the new value-shape requirement. These
        # were the reported false-positive rows, measured BLOCKING (exit 1)
        # against the un-fixed scanner before this fix landed. Kept as plain
        # literals (not MF6-obfuscated): neither `default` nor `config.ApiKey`
        # contains a digit or a quote, so no contiguous trigger exists here
        # even pre-obfuscation -- that absence IS the fix being exercised.
        "p32_cancellationToken_param_default": "public async Task RunAsync(CancellationToken cancellationToken = default)",
        "p33_cancellationToken_var_default": "public Task StopAsync(CancellationToken token = default) => Task.CompletedTask;",
        "p34_apikey_member_access": "private readonly string apiKey = config.ApiKey;",
        # Declaration-value shapes named explicitly in the fix contract: none
        # of these bare keywords contains a digit, so the value-shape
        # requirement rejects all of them regardless of the identifier anchor.
        "p35_token_null": "let token = null;",
        "p36_token_none": "token = None",
        "p37_token_nil": "var token = nil",
        "p38_token_undefined": "let token = undefined;",
        "p39_token_empty_string": 'token = ""',
        "p40_token_end_of_line": "token =",
        "p41_token_await_call": "var token = await GetTokenAsync(ct);",
        # Declaration-value negative for the other 2 reworked patterns
        # (token/api-key already covered above): neither bare `null` contains
        # a digit, so both stay clean under the same value-shape requirement.
        "p43_password_declaration": "var password = null;",
        "p44_secret_declaration": "var secret = null;",
        # Anchor rejects the keyword as an incidental substring of an
        # unrelated identifier with no segment boundary before it, even when
        # a real leak-shaped value follows. Assembled per MF6.
        "p42_anchor_incidental_myatoken": _join("my", "a", "to", "ken", " = ", '"', "a1b2c3d4e5f6g7h8ijk", '"'),
        # NEW (2026-07-27 F1 fix guard): the SAME declaration shapes as
        # p35-p38, now in SINGLE-quoted and BACKTICK-quoted form, must stay
        # clean under the new delimiter-class branch -- it must not become a
        # blanket "anything quoted blocks" rule. Kept as plain literals (not
        # MF6-obfuscated): none of `default` / `None` / `null` / `ghp_xxxx`
        # contains a digit, so no contiguous trigger exists even pre-fix.
        "p45_token_single_quoted_default": "token = 'default'",
        "p46_token_single_quoted_none": "token = 'None'",
        "p47_token_single_quoted_null": "token = 'null'",
        "p48_token_backtick_default": "token = `default`",
        "p49_token_single_quoted_ghp_example": "token = 'ghp_xxxx'",
        # F4 regression pin (see the matching b41 in block_rows()): a digit
        # centered in a 9-char value (4 chars before, 4 after) stays clean --
        # the effective floor is 10, not the nominal 6, when the digit cannot
        # land with >=5 chars on either side. Plain literal: 9 chars total
        # with no quote/keyword-adjacency trigger beyond this value shape.
        "p50_token_centered_digit_below_floor": "token = abcd5efgh",
        # NEW (2026-07-27 F7 fix): the delimiter class from the F1 fix
        # (`[^[:alnum:][:space:]]`) matched far more than quote characters --
        # identifier and statement punctuation too (`_ ( [ { < . / ; , -`),
        # which C-family/scripting code supplies a CLOSING member of for free.
        # These four rows are the exact false-positive reproduction (none
        # contains any secret): a private-field assignment, a private call, a
        # path-valued config line, and a documentation placeholder. All four
        # measured BLOCKING against the un-narrowed class before this fix
        # landed; the delimiter class was narrowed to exclude identifier and
        # statement punctuation so all four now PASS. Kept as plain literals
        # (no MF6 obfuscation needed): none contains a digit, so no
        # contiguous trigger exists even pre-fix.
        "p51_private_field_assignment": "token = _refreshTokenValue;",
        "p52_private_call_no_args": "token = _load_token_value()",
        "p53_secrets_mount_path_value": "password: /run/secrets/db_password",
        "p54_doc_placeholder_angle_upper": "api_key = <YOUR_API_KEY>",
        # The finding in one line: idiomatic C# dependency-injection member
        # access with a leading underscore on the field. p34 above
        # (`apiKey = config.ApiKey;`) only stayed clean because `config` has
        # no underscore -- this row is the same member-access shape with the
        # underscore the admission fixture happened to omit.
        "p55_csharp_di_underscored_member_access": "apiKey = _configuration.ApiKey;",
    }


@unittest.skipIf(_git() is None, "needs git on PATH")
class TestPublicationSafetyScanner(unittest.TestCase):
    def _run_cached(
        self,
        scanner: Path,
        content: str,
        env_overrides: dict | None = None,
        filename: str = "fixture.txt",
    ) -> int:
        """Stage `content` as a file in a throwaway repo and run the REAL scanner
        in its production --cached tracked mode (cwd = the throwaway repo). The
        scanner resolves its allowlist owner via its own absolute source path, so
        it uses the real reference hook regardless of cwd. Returns the exit code."""
        return self._run_cached_full(scanner, content, env_overrides=env_overrides, filename=filename)[0]

    def _run_cached_full(
        self,
        scanner: Path,
        content: str,
        env_overrides: dict | None = None,
        filename: str = "fixture.txt",
    ) -> tuple[int, str]:
        """Same as `_run_cached` but also returns stdout, for tests that must
        inspect the scanner's own self-reported RESULT text (2026-07-26
        hardening: check-git-push-gate.py step 8 branch (b) now keys on this
        text, not just the exit code)."""
        proc = self._run_cached_process(scanner, content, env_overrides=env_overrides, filename=filename)
        return proc.returncode, proc.stdout

    def _run_cached_process(
        self,
        scanner: Path,
        content: str,
        env_overrides: dict | None = None,
        filename: str = "fixture.txt",
    ) -> subprocess.CompletedProcess[str]:
        """Run one real cached scan and retain both output channels for callers."""
        git = _git()
        with tempfile.TemporaryDirectory() as td:
            subprocess.run([git, "init", "-q", td], check=True, capture_output=True)
            subprocess.run([git, "-C", td, "config", "user.email", "t@t"], check=True, capture_output=True)
            subprocess.run([git, "-C", td, "config", "user.name", "t"], check=True, capture_output=True)
            fixture = Path(td) / filename
            fixture.parent.mkdir(parents=True, exist_ok=True)
            fixture.write_text(content + "\n", encoding="utf-8")
            subprocess.run([git, "-C", td, "add", filename], check=True, capture_output=True)
            env = dict(os.environ)
            if env_overrides:
                env.update(env_overrides)
            proc = subprocess.run(
                [sys.executable, str(scanner)],
                cwd=td,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
            )
            return proc

    def _run_cached_batch_full(
        self,
        scanner: Path,
        rows: dict[str, str],
    ) -> tuple[int, str]:
        """Stage one named fixture row per line and retain scanner findings."""
        proc = self._run_cached_process(scanner, "\n".join(rows.values()))
        return proc.returncode, proc.stdout + proc.stderr

    def test_cached_batch_reports_each_fixture_line(self) -> None:
        rows = {
            "first": block_rows()["b01_win_home"],
            "second": block_rows()["b14_aws"],
        }
        rc, out = self._run_cached_batch_full(CODEX_SCANNER, rows)
        self.assertEqual(rc, 1)
        _assert_batch_finding_lines(self, out, rows)

    def _assert_cached_block_batch(self, scanner: Path, rows: dict[str, str]) -> None:
        rc, out = self._run_cached_batch_full(scanner, rows)
        self.assertEqual(rc, 1, f"{scanner.name} must BLOCK the fixture batch")
        _assert_batch_finding_lines(self, out, rows)

    def _assert_cached_pass_batch(self, scanner: Path, rows: dict[str, str]) -> None:
        rc, out = self._run_cached_batch_full(scanner, rows)
        self.assertEqual(rc, 0, f"{scanner.name} must PASS the fixture batch: {out!r}")

    def _run_cached_nothing_staged(self, scanner: Path) -> tuple[int, str]:
        """Run the scanner in a real repo with NOTHING staged at all -- the
        live-failure shape (2026-07-25/26): after a commit, the index equals
        HEAD, so `git diff --cached` is empty and the scanner examines nothing.
        Distinct from `_run_cached`, which always stages exactly one file."""
        git = _git()
        with tempfile.TemporaryDirectory() as td:
            subprocess.run([git, "init", "-q", td], check=True, capture_output=True)
            subprocess.run([git, "-C", td, "config", "user.email", "t@t"], check=True, capture_output=True)
            subprocess.run([git, "-C", td, "config", "user.name", "t"], check=True, capture_output=True)
            proc = subprocess.run(
                [sys.executable, str(scanner)],
                cwd=td,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            return proc.returncode, proc.stdout

    def test_block_rows_exit_1(self) -> None:
        for scanner in SCANNERS:
            with self.subTest(scanner=scanner.parent.parent.name):
                self._assert_cached_block_batch(scanner, block_rows())

    def test_pass_rows_exit_0(self) -> None:
        for scanner in SCANNERS:
            with self.subTest(scanner=scanner.parent.parent.name):
                self._assert_cached_pass_batch(scanner, pass_rows())

    def test_clean_repo_exits_0(self) -> None:
        for scanner in SCANNERS:
            with self.subTest(scanner=scanner.parent.parent.name):
                self.assertEqual(self._run_cached(scanner, "nothing machine-local here"), 0)

    def test_clean_nonempty_scan_reports_tracked_examined_count(self) -> None:
        # 2026-07-26 hardening (D2/S6): a REAL clean scan over a non-empty
        # staged set must self-report a distinguishable "tracked, examined N
        # files" result -- this is the exact text check-git-push-gate.py's
        # SCAN_CLEAN_TRACKED_REGEX matches against tool OUTPUT.
        for scanner in SCANNERS:
            with self.subTest(scanner=scanner.parent.parent.name):
                rc, out = self._run_cached_full(scanner, "nothing machine-local here")
                self.assertEqual(rc, 0)
                self.assertIn("publication-safety: clean (tracked, examined 1 file)", out)

    def test_nothing_staged_exits_0_but_reports_zero_examined(self) -> None:
        # THE LIVE FAILURE (2026-07-25/26): with nothing staged at all (the
        # ordinary post-commit state, where the index already equals HEAD),
        # the scan still exits 0 -- but it must be able to tell a caller that
        # it examined NOTHING, so an "examined 0" result is never mistaken for
        # a real pass. This is the exact defect the push-gate hardening closes:
        # an empty scan must never read as a pass.
        for scanner in SCANNERS:
            with self.subTest(scanner=scanner.parent.parent.name):
                rc, out = self._run_cached_nothing_staged(scanner)
                self.assertEqual(rc, 0, "an empty staged set is not itself a finding")
                self.assertIn("examined 0 files", out)
                # And, just as importantly, it must NOT accidentally satisfy
                # the push gate's non-empty regex (`[1-9]\d*`).
                self.assertNotRegex(out, r"examined [1-9]\d* files?")

    def test_path_mode_clean_scan_reports_path_not_tracked(self) -> None:
        # A `--path` fixture-testing invocation must self-report scan MODE
        # "path", never "tracked" -- so it can never launder as push-gate
        # evidence for what is actually staged (§3.3-parallel guard: the
        # narrowed push-gate mechanism keys on the literal word "tracked").
        # `--path` mode still requires a repo context (the scanner
        # unconditionally `cd`s to `git rev-parse --show-toplevel`), so the
        # fixture directory is git-init'd even though nothing is staged there.
        git = _git()
        for scanner in SCANNERS:
            with self.subTest(scanner=scanner.parent.parent.name):
                with tempfile.TemporaryDirectory() as td:
                    subprocess.run([git, "init", "-q", td], check=True, capture_output=True)
                    fixture = Path(td) / "clean.txt"
                    fixture.write_text("nothing machine-local here\n", encoding="utf-8")
                    proc = subprocess.run(
                        [sys.executable, str(scanner), "--path", str(fixture)],
                        cwd=td,
                        capture_output=True, text=True, encoding="utf-8",
                    )
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    self.assertIn("publication-safety: clean (path, examined 1 file)", proc.stdout)
                    self.assertNotIn("tracked", proc.stdout)

    def test_path_mode_directory_reports_actual_file_count_not_hardcoded_one(self) -> None:
        # Honesty regression (2026-07-26 adversarial-gate Finding 11a): a
        # `--path` argument naming a DIRECTORY with several files must report
        # the real count it walked, not a hardcoded "1" (the scan_files array
        # always holds exactly one entry -- the `--path` argument itself --
        # regardless of whether it names a file or a directory containing
        # many). Path mode can never satisfy the push gate regardless of
        # count (it is tagged "path", never "tracked"), so this was never a
        # security hole -- only a false record of what was scanned.
        git = _git()
        for scanner in SCANNERS:
            with self.subTest(scanner=scanner.parent.parent.name):
                with tempfile.TemporaryDirectory() as td:
                    subprocess.run([git, "init", "-q", td], check=True, capture_output=True)
                    fixture_dir = Path(td) / "fixtures"
                    fixture_dir.mkdir()
                    (fixture_dir / "a.txt").write_text("nothing machine-local here\n", encoding="utf-8")
                    (fixture_dir / "b.txt").write_text("also nothing machine-local here\n", encoding="utf-8")
                    proc = subprocess.run(
                        [sys.executable, str(scanner), "--path", str(fixture_dir)],
                        cwd=td,
                        capture_output=True, text=True, encoding="utf-8",
                    )
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    self.assertIn(
                        "publication-safety: clean (path, examined 2 files)", proc.stdout,
                        f"expected the real walked count (2), got: {proc.stdout!r}",
                    )

    def test_env_filename_blocks_even_without_secret_content(self) -> None:
        for scanner in SCANNERS:
            with self.subTest(scanner=scanner.parent.parent.name):
                self.assertEqual(self._run_cached(scanner, "PUBLIC_VALUE=1", filename=".env"), 1)

    def test_secret_md_filename_blocks_in_any_casing_even_without_secret_content(self) -> None:
        # The credential-filename block is format-independent AND
        # case-insensitive: Windows (the pack's primary platform) has a
        # case-insensitive filesystem, so every casing of the staged
        # credential filename must block identically, innocuous content
        # included. (Filename assembled per MF6.)
        for scanner in SCANNERS:
            for filename in ("SECRET" + ".md", "secret" + ".md", "Secret" + ".md"):
                with self.subTest(scanner=scanner.parent.parent.name, filename=filename):
                    self.assertEqual(
                        self._run_cached(scanner, "innocuous release checklist notes", filename=filename),
                        1,
                        f"staged {filename!r} must BLOCK (exit 1) regardless of content",
                    )

    def test_scanner_file_itself_is_scanned_for_real_secret_content(self) -> None:
        # MF6 note: the local variable is deliberately named `leak` -- naming
        # it after the marker it holds would form an assignment line that is
        # itself a scanner trip when THIS file is staged.
        for scanner in SCANNERS:
            with self.subTest(scanner=scanner.parent.parent.name):
                leak = "pass" + "word" + ": hunter2"
                self.assertEqual(
                    self._run_cached(
                        scanner,
                        f"nonpath_patterns=(\\n  {leak!r}\\n)",
                        filename="scripts/check-publication-safety.py",
                    ),
                    1,
                )

    def test_scanner_file_allows_exact_intentional_regex_catalog_lines(self) -> None:
        # Catalog entries assembled per MF6: the marker phrases must never sit
        # contiguously in this tracked source, only in the staged fixture.
        catalog = "\n".join(
            [
                _join("re.compile(r\"BEGIN RSA PRIVATE", " KEY\"),"),
                _join("re.compile(r\"BEGIN OPENSSH PRIVATE", " KEY\"),"),
                _join("re.compile(r\"BEGIN PRIVATE", " KEY\"),"),
                _join("re.compile(r\"private", "_key\"),"),
                _join("re.compile(r\"secret", "_key\"),"),
            ]
        )
        for scanner in SCANNERS:
            with self.subTest(scanner=scanner.parent.parent.name):
                self.assertEqual(
                    self._run_cached(
                        scanner,
                        catalog,
                        filename="scripts/check-publication-safety.py",
                    ),
                    0,
                )

    def test_scanner_file_blocks_catalog_line_with_secret_comment(self) -> None:
        leak = "pass" + "word" + ": hunter2"
        for scanner in SCANNERS:
            with self.subTest(scanner=scanner.parent.parent.name):
                self.assertEqual(
                    self._run_cached(
                        scanner,
                        _join("re.compile(r\"secret", "_key\"), # ", leak),
                        filename="scripts/check-publication-safety.py",
                    ),
                    1,
                )

    def test_scanner_file_blocks_secret_suffix_on_other_intentional_prefixes(self) -> None:
        leak = "pass" + "word" + ": hunter2"
        prefixes = (
            '_VALUE = "safe"  # ',
            '_DIGIT_SHAPE = "safe"  # ',
            '_QUOTED = "safe"  # ',
            '_BARE = "safe"  # ',
            "_KEYWORDS = ()  # ",
            "_VALUE_PATTERNS = ()  # ",
            '"""scanner docs"""  # ',
        )
        for scanner in SCANNERS:
            for prefix in prefixes:
                with self.subTest(scanner=scanner.parent.parent.name, prefix=prefix):
                    self.assertEqual(
                        self._run_cached(
                            scanner,
                            prefix + leak,
                            filename="scripts/check-publication-safety.py",
                        ),
                        1,
                    )

    def test_scanner_own_source_passes_only_under_its_own_filename(self) -> None:
        # Gate self-block regression (Wave A audit): the REAL scanner source
        # must pass staged under its own filename (its pattern-catalog entries
        # and marker-bearing comments are its own intentional content), while
        # the SAME content staged under any other filename must still BLOCK --
        # the self-exemption is keyed to the scanner's filename and is not a
        # general hole.
        content = CODEX_SCANNER.read_text(encoding="utf-8")
        for scanner in SCANNERS:
            with self.subTest(scanner=scanner.parent.parent.name):
                self.assertEqual(
                    self._run_cached(scanner, content, filename="scripts/check-publication-safety.py"),
                    0,
                    "scanner source under its own name must PASS (no gate self-block)",
                )
                self.assertEqual(
                    self._run_cached(scanner, content, filename="scripts/some-other-script.py"),
                    1,
                    "scanner source under any other name must still BLOCK",
                )


@unittest.skipIf(_git() is None, "needs git on PATH")
class TestPublicationSafetyScannerRangeMode(unittest.TestCase):
    """Regression tests for `--range <remote> <dst>` (2026-07-27,
    work-items/active/2026-07-26-push-gate-range-receipt/): the scanner's
    subject becomes the commit set about to be PUBLISHED
    (`<tip> --not --remotes=<remote>`), read from the COMMITTED BLOB at
    `tip` -- never the working tree, never the index -- rather than the
    staged index `tracked` mode reads. See that scanner's own `--range`
    branch comment for the full design citation."""

    def _init_range_repo(self, td: Path) -> Path:
        """git-init a bare 'origin.git' and a working 'repo' next to it,
        wire 'repo' to 'origin' as remote `origin`, and publish one
        throwaway seed commit so `--range origin main` has a real remote
        tracking ref to diff against. Returns the working repo path."""
        git = _git()
        origin = td / "origin.git"
        repo = td / "repo"
        subprocess.run([git, "init", "-q", "--bare", str(origin)], check=True, capture_output=True)
        subprocess.run([git, "init", "-q", str(repo)], check=True, capture_output=True)
        subprocess.run([git, "-C", str(repo), "config", "user.email", "t@t"], check=True, capture_output=True)
        subprocess.run([git, "-C", str(repo), "config", "user.name", "t"], check=True, capture_output=True)
        subprocess.run(
            [git, "-C", str(repo), "remote", "add", "origin", str(origin)], check=True, capture_output=True
        )
        (repo / "seed.txt").write_text("seed content, nothing machine-local here\n", encoding="utf-8")
        subprocess.run([git, "-C", str(repo), "add", "seed.txt"], check=True, capture_output=True)
        subprocess.run([git, "-C", str(repo), "commit", "-q", "-m", "seed"], check=True, capture_output=True)
        subprocess.run(
            [git, "-C", str(repo), "push", "-q", "origin", "HEAD:refs/heads/main"],
            check=True, capture_output=True,
        )
        return repo

    def _commit_file(self, repo: Path, filename: str, content: str, message: str = "add file") -> None:
        git = _git()
        path = repo / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content + "\n", encoding="utf-8")
        subprocess.run([git, "-C", str(repo), "add", filename], check=True, capture_output=True)
        subprocess.run([git, "-C", str(repo), "commit", "-q", "-m", message], check=True, capture_output=True)

    def _rm_file(self, repo: Path, filename: str, message: str = "remove file") -> None:
        git = _git()
        subprocess.run([git, "-C", str(repo), "rm", "-q", filename], check=True, capture_output=True)
        subprocess.run([git, "-C", str(repo), "commit", "-q", "-m", message], check=True, capture_output=True)

    def _run_range(self, scanner: Path, repo: Path, remote: str, dst: str) -> tuple[int, str, str]:
        proc = subprocess.run(
            [sys.executable, str(scanner), "--range", remote, dst],
            cwd=str(repo),
            capture_output=True, text=True, encoding="utf-8",
        )
        return proc.returncode, proc.stdout, proc.stderr

    def test_range_mode_clean_scan_reports_remote_dst_tip_receipt(self) -> None:
        # The exact receipt shape check-git-push-gate.py's SCAN_CLEAN_RANGE_
        # REGEX matches: mode word "range", a non-empty examined count, and
        # the remote/dst/tip fields the gate compares against push argv.
        for scanner in SCANNERS:
            with self.subTest(scanner=scanner.parent.parent.name):
                with tempfile.TemporaryDirectory() as td:
                    repo = self._init_range_repo(Path(td))
                    self._commit_file(repo, "b.txt", "clean content, nothing machine-local here")
                    git = _git()
                    tip = subprocess.run(
                        [git, "-C", str(repo), "rev-parse", "HEAD"],
                        check=True, capture_output=True, text=True,
                    ).stdout.strip()
                    rc, out, err = self._run_range(scanner, repo, "origin", "claude")
                    self.assertEqual(rc, 0, err)
                    self.assertRegex(
                        out,
                        rf"^publication-safety: clean \(range, receipt=v2, files=1, commits=1, "
                        rf"commit-set=[0-9a-f]{{64}}, messages=complete, remote=origin, "
                        rf"dst=claude, tip={tip}\)\n?$",
                    )

    def test_range_mode_empty_range_reports_zero_and_is_not_creditable(self) -> None:
        # An empty outgoing selection is uncertainty at the publication gate:
        # it refuses and can never mint a zero-commit clean receipt.
        for scanner in SCANNERS:
            with self.subTest(scanner=scanner.parent.parent.name):
                with tempfile.TemporaryDirectory() as td:
                    repo = self._init_range_repo(Path(td))
                    rc, out, err = self._run_range(scanner, repo, "origin", "main")
                    self.assertEqual(rc, 2, err)
                    self.assertEqual(out, "")
                    self.assertIn("PS-MSG-COVERAGE", err)
                    self.assertNotIn("publication-safety: clean", err)

    def test_range_mode_reads_content_at_tip_not_working_tree(self) -> None:
        # O16, the single most important range-mode content-source property:
        # a file DIRTY in the working tree with a planted secret but CLEAN at
        # tip must PASS (exit 0) -- proving content comes from the committed
        # blob, never disk.
        leak = "pass" + "word" + ": hunter2"
        for scanner in SCANNERS:
            with self.subTest(scanner=scanner.parent.parent.name):
                with tempfile.TemporaryDirectory() as td:
                    repo = self._init_range_repo(Path(td))
                    self._commit_file(repo, "b.txt", "clean content, nothing machine-local here")
                    (repo / "b.txt").write_text(leak + "\n", encoding="utf-8")  # dirty disk, NOT staged/committed
                    rc, out, err = self._run_range(scanner, repo, "origin", "claude")
                    self.assertEqual(rc, 0, err)
                    self.assertIn("publication-safety: clean (range,", out)

    def test_range_mode_blocks_secret_committed_within_range(self) -> None:
        # The mirror case: a secret committed (present at tip) blocks, even
        # though it was never staged in THIS invocation's index (there is no
        # index-staging step in this flow at all -- the commit already
        # happened in an earlier turn, exactly the operator's workflow).
        leak = "pass" + "word" + ": hunter2"
        for scanner in SCANNERS:
            with self.subTest(scanner=scanner.parent.parent.name):
                with tempfile.TemporaryDirectory() as td:
                    repo = self._init_range_repo(Path(td))
                    self._commit_file(repo, "c.txt", leak)
                    rc, out, err = self._run_range(scanner, repo, "origin", "claude")
                    self.assertEqual(rc, 1, out)
                    self.assertIn("publication-safety scan found potential tracked-content leak markers", err)

    def test_range_mode_add_then_delete_path_skipped_not_over_blocked(self) -> None:
        # FM-5: a path added then deleted again within the range has NO
        # content at `tip` -- it must be silently skipped (not counted, not
        # an error), never over-blocked.
        for scanner in SCANNERS:
            with self.subTest(scanner=scanner.parent.parent.name):
                with tempfile.TemporaryDirectory() as td:
                    repo = self._init_range_repo(Path(td))
                    self._commit_file(repo, "gone.txt", "temporary, nothing machine-local here")
                    self._rm_file(repo, "gone.txt")
                    rc, out, err = self._run_range(scanner, repo, "origin", "claude")
                    self.assertEqual(rc, 0, err)
                    self.assertRegex(
                        out,
                        r"^publication-safety: clean \(range, receipt=v2, files=0, commits=2, "
                        r"commit-set=[0-9a-f]{64}, messages=complete, remote=origin, "
                        r"dst=claude, tip=[0-9a-f]{40,64}\)\n?$",
                    )

    def test_range_mode_self_exemption_for_scanner_copy_inside_range(self) -> None:
        # Guard G3: the scanner's own copy, committed inside a scanned range,
        # must self-exempt under the FOUR-field commit-mode grep shape
        # (`<tip>:<path>:<lineno>:<content>`), not self-block on its own
        # pattern-catalog lines.
        content = CODEX_SCANNER.read_text(encoding="utf-8")
        for scanner in SCANNERS:
            with self.subTest(scanner=scanner.parent.parent.name):
                with tempfile.TemporaryDirectory() as td:
                    repo = self._init_range_repo(Path(td))
                    self._commit_file(repo, "scripts/check-publication-safety.py", content, message="add scanner")
                    rc, out, err = self._run_range(scanner, repo, "origin", "claude")
                    self.assertEqual(rc, 0, err)

    def test_range_mode_rejects_unconfigured_remote_name_and_redacts_value(self) -> None:
        # F6/F7: an exact configured-remote-name check, and the rejected
        # value must never be echoed (it may carry credentials).
        secret_url = "https://user:token123@example.com/x.git"
        for scanner in SCANNERS:
            with self.subTest(scanner=scanner.parent.parent.name):
                with tempfile.TemporaryDirectory() as td:
                    repo = self._init_range_repo(Path(td))
                    rc, out, err = self._run_range(scanner, repo, secret_url, "claude")
                    self.assertEqual(rc, 2)
                    self.assertNotIn(secret_url, err)
                    self.assertNotIn("token123", err)
                    self.assertIn("id=PS-MSG-RANGE reason=remote", err)

    def test_range_mode_rejects_glob_remote_value(self) -> None:
        # F7: `--remotes=` is glob-matched by git; a glob value must be
        # rejected by the exact-name check rather than silently under- or
        # over-scanning.
        for scanner in SCANNERS:
            with self.subTest(scanner=scanner.parent.parent.name):
                with tempfile.TemporaryDirectory() as td:
                    repo = self._init_range_repo(Path(td))
                    rc, out, err = self._run_range(scanner, repo, "*", "claude")
                    self.assertEqual(rc, 2)
                    self.assertIn("id=PS-MSG-RANGE reason=remote", err)

    def test_range_mode_missing_arguments_errors(self) -> None:
        for scanner in SCANNERS:
            with self.subTest(scanner=scanner.parent.parent.name):
                with tempfile.TemporaryDirectory() as td:
                    repo = self._init_range_repo(Path(td))
                    proc = subprocess.run(
                        [sys.executable, str(scanner), "--range", "origin"],
                        cwd=str(repo),
                        capture_output=True, text=True, encoding="utf-8",
                    )
                    self.assertEqual(proc.returncode, 2)


@unittest.skipIf(_git() is None, "needs git on PATH")
class TestPublicationSafetyScannerV2(unittest.TestCase):
    """Item-6 contract guards target the universal owner directly."""

    def _git_run(
        self, repo: Path, *args: str, input_text: str | None = None, check: bool = True
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            [_git(), "-C", str(repo), *args],
            input=input_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=check,
        )

    def _init_range_repo(self, root: Path, *, publish_seed: bool = True) -> Path:
        origin = root / "origin.git"
        repo = root / "repo"
        subprocess.run([_git(), "init", "-q", "--bare", str(origin)], check=True)
        subprocess.run([_git(), "init", "-q", str(repo)], check=True)
        self._git_run(repo, "config", "user.email", "t@t")
        self._git_run(repo, "config", "user.name", "t")
        self._git_run(repo, "remote", "add", "origin", str(origin))
        self._commit(repo, "seed.txt", "clean seed", "seed")
        if publish_seed:
            self._git_run(repo, "push", "-q", "origin", "HEAD:refs/heads/main")
        return repo

    def _commit(self, repo: Path, name: str, content: str, message: str) -> str:
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content + "\n", encoding="utf-8")
        self._git_run(repo, "add", name)
        self._git_run(repo, "commit", "-q", "-F", "-", input_text=message)
        return self._git_run(repo, "rev-parse", "HEAD").stdout.strip()

    def _run_range(self, repo: Path, remote: str = "origin", dst: str = "main") -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(CANONICAL_SCANNER), "--range", remote, dst],
            cwd=repo,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def _run_path(self, content: str) -> subprocess.CompletedProcess:
        return self._run_path_process(content)

    def _run_path_process(self, content: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            subprocess.run([_git(), "init", "-q", str(repo)], check=True)
            fixture = repo / "fixture.txt"
            fixture.write_text(content + "\n", encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(CANONICAL_SCANNER), "--path", str(fixture)],
                cwd=repo,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

    def _run_path_batch_full(self, rows: dict[str, str]) -> tuple[int, str]:
        """Run one real path-mode scan over one named fixture row per line."""
        proc = self._run_path_process("\n".join(rows.values()))
        return proc.returncode, proc.stdout + proc.stderr

    def _expected_digest(self, rows: list[str]) -> str:
        ordered = [value.lower() for value in rows]
        framed = b"publication-safety-range-receipt-v2\0" + b"\0".join(
            value.encode("ascii") for value in ordered
        )
        return hashlib.sha256(framed).hexdigest()

    def _leak_message(self, label: str) -> str:
        return _join(label, "\n\n", "to", "ken", " = ", "A1B2C3D4E5F6G7H8IJK")

    def test_uppercase_identifier_polarity_matrix(self) -> None:
        families = {
            "password": ("password", "service_password", "servicePassword", "DBPassword", "DBPASSWORD"),
            "secret": ("secret", "service_secret", "serviceSecret", "AWSSecret", "AWSSECRET"),
            "token": ("token", "service_token", "serviceToken", "APIToken", "APITOKEN"),
            "api-key": ("api_key", "service_api_key", "serviceApiKey", "XApiKey", "MYAPIKEY"),
        }
        values = ("A1B2C3D4E5F6G7H8IJK", '"A1B2C3D4E5F6G7H8IJK"')
        blocked_rows: dict[str, str] = {}
        for family, identifiers in families.items():
            for identifier in identifiers:
                for value in values:
                    quoted = "quoted" if value.startswith('"') else "bare"
                    blocked_rows[f"{family}:{identifier}:{quoted}"] = f"{identifier} = {value}"
        self.assertEqual(len(blocked_rows), 40)
        rc, out = self._run_path_batch_full(blocked_rows)
        self.assertEqual(rc, 1, out)
        _assert_batch_finding_lines(self, out, blocked_rows)
        rc, out = self._run_path_batch_full(block_rows())
        self.assertEqual(rc, 1, out)
        _assert_batch_finding_lines(self, out, block_rows())
        rc, out = self._run_path_batch_full(pass_rows())
        self.assertEqual(rc, 0, out)
        pass_rows_for_matrix = {
            "incidental-myatoken": "myatoken = A1B2C3D4E5F6G7H8IJK",
            "declaration-cancellation-token": "CancellationToken cancellationToken = default",
        }
        rc, out = self._run_path_batch_full(pass_rows_for_matrix)
        self.assertEqual(rc, 0, out)

    def test_range_message_exactly_once(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = self._init_range_repo(Path(td))
            self._commit(repo, "one.txt", "clean one", "first clean message")
            self._commit(repo, "two.txt", "clean two", "second clean message")
            selected = self._git_run(
                repo, "rev-list", "--topo-order", "HEAD", "--not", "--remotes=origin"
            ).stdout.splitlines()
            proc = self._run_range(repo)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn(f"commits={len(selected)}", proc.stdout)
            self.assertIn(f"commit-set={self._expected_digest(selected)}", proc.stdout)
            self.assertIn("messages=complete", proc.stdout)

    def test_range_message_row_mutation(self) -> None:
        module = _load_canonical_scanner("_scanner_v2_mutation")
        self.assertTrue(hasattr(module, "_canonical_commit_ids"))
        rows = ["1" * 40, "2" * 40, "3" * 40]
        self.assertEqual(module._canonical_commit_ids(rows), tuple(rows))
        for mutation in (rows[:-1], rows + [rows[-1]], [rows[0], rows[1], "4" * 40]):
            with self.subTest(mutation=tuple(mutation)):
                if len(mutation) != len(set(mutation)):
                    with self.assertRaises(ValueError):
                        module._canonical_commit_ids(mutation)
                else:
                    self.assertNotEqual(self._expected_digest(rows), self._expected_digest(mutation))

    def test_range_commit_graph_matrix(self) -> None:
        cases = ("non-tip-body", "trailer", "rename", "delete", "binary", "add-delete", "initial", "other-remote", "merge")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                repo = self._init_range_repo(root, publish_seed=case in {"non-tip-body", "trailer", "rename", "delete", "binary", "add-delete", "merge"})
                message = self._leak_message(case)
                if case == "non-tip-body":
                    self._commit(repo, "a.txt", "clean a", message)
                    self._commit(repo, "b.txt", "clean b", "clean tip")
                elif case == "trailer":
                    self._commit(repo, "a.txt", "clean a", "clean subject\n\nSigned-off-by: t\n" + message)
                elif case == "rename":
                    self._git_run(repo, "mv", "seed.txt", "renamed.txt")
                    self._git_run(repo, "commit", "-q", "-F", "-", input_text=message)
                elif case == "delete":
                    self._git_run(repo, "rm", "seed.txt")
                    self._git_run(repo, "commit", "-q", "-F", "-", input_text=message)
                elif case == "binary":
                    (repo / "binary.bin").write_bytes(b"\0\1\2")
                    self._git_run(repo, "add", "binary.bin")
                    self._git_run(repo, "commit", "-q", "-F", "-", input_text=message)
                elif case == "add-delete":
                    self._commit(repo, "gone.txt", "clean transient", message)
                    self._git_run(repo, "rm", "gone.txt")
                    self._git_run(repo, "commit", "-q", "-m", "clean delete")
                elif case == "initial":
                    self._commit(repo, "initial.txt", "clean initial", message)
                elif case == "other-remote":
                    backup = root / "backup.git"
                    subprocess.run([_git(), "init", "-q", "--bare", str(backup)], check=True)
                    self._git_run(repo, "remote", "add", "backup", str(backup))
                    self._commit(repo, "other.txt", "clean other", message)
                    self._git_run(repo, "push", "-q", "backup", "HEAD:refs/heads/main")
                else:
                    base = self._git_run(repo, "branch", "--show-current").stdout.strip()
                    self._git_run(repo, "checkout", "-q", "-b", "side")
                    self._commit(repo, "side.txt", "clean side", "clean side")
                    self._git_run(repo, "checkout", "-q", base)
                    self._commit(repo, "base.txt", "clean base", "clean base")
                    self._git_run(repo, "merge", "--no-ff", "side", "-q", "-m", message)
                proc = self._run_range(repo)
                self.assertEqual(proc.returncode, 1, f"case={case} out={proc.stdout!r} err={proc.stderr!r}")
                self.assertNotIn("A1B2C3D4E5F6G7H8IJK", proc.stdout + proc.stderr)

    def test_range_message_zero_file_nonzero_commit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = self._init_range_repo(Path(td))
            self._git_run(repo, "rm", "seed.txt")
            self._git_run(repo, "commit", "-q", "-m", "clean delete")
            proc = self._run_range(repo)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("files=0, commits=1", proc.stdout)
            self.assertIn("messages=complete", proc.stdout)

    def test_range_fail_closed_matrix(self) -> None:
        module = _load_canonical_scanner("_scanner_v2_failures")
        for name in ("Refusal", "_canonical_commit_ids", "_decode_commit_message", "_parse_batch_header"):
            self.assertTrue(hasattr(module, name), name)
        with self.assertRaises(ValueError):
            module._canonical_commit_ids(["x" * 40])
        with self.assertRaises(ValueError):
            module._canonical_commit_ids(["1" * 40, "1" * 40])
        failures = (
            (b"tree " + b"1" * 40 + b"\nencoding latin1\n\nclean", "PS-MSG-DECODE"),
            (b"tree " + b"1" * 40 + b"\n\n\xff", "PS-MSG-DECODE"),
            (b"tree " + b"1" * 40 + b"\n\n" + b"a" * (1_048_576 + 1), "PS-MSG-LIMIT"),
        )
        for raw, failure_id in failures:
            with self.subTest(failure_id=failure_id):
                outcome = module._decode_commit_message(raw)
                self.assertEqual(outcome.failure_id, failure_id)
        for header in (b"missing", b"1" * 40 + b" blob 2", b"2" * 40 + b" commit 2", b"1" * 40 + b" commit nope"):
            with self.subTest(header=header[:8]):
                outcome = module._parse_batch_header(header, "1" * 40, "commit")
                self.assertEqual(outcome.failure_id, "PS-MSG-FRAME")
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            subprocess.run([_git(), "init", "-q", str(repo)], check=True)
            proc = self._run_range(repo, "missing")
            self.assertEqual(proc.returncode, 2)
            self.assertIn("PS-MSG-RANGE", proc.stderr)
            self.assertNotIn("publication-safety: clean", proc.stdout + proc.stderr)

    def test_range_tip_changed(self) -> None:
        module = _load_canonical_scanner("_scanner_v2_tip")
        self.assertTrue(hasattr(module, "_confirm_tip"))
        refusal = module._confirm_tip("1" * 40, lambda: "2" * 40)
        self.assertEqual(refusal.failure_id, "PS-MSG-TIP-CHANGED")

    def test_receipt_v2_canonicalization(self) -> None:
        module = _load_canonical_scanner("_scanner_v2_receipt")
        self.assertTrue(hasattr(module, "_serialize_range_receipt_v2"))
        rows = ["2" * 40, "1" * 40]
        line = module._serialize_range_receipt_v2(0, rows, "origin one", "refs/heads/topic", "2" * 40)
        self.assertEqual(
            line,
            "publication-safety: clean (range, receipt=v2, files=0, commits=2, "
            f"commit-set={self._expected_digest(rows)}, messages=complete, "
            "remote=origin%20one, dst=refs%2Fheads%2Ftopic, tip=" + "2" * 40 + ")",
        )
        self.assertFalse(hasattr(module, "_serialize_empty_range_v2"))

    def test_redacted_finding_output(self) -> None:
        sentinel = "A1B2C3D4E5F6G7H8IJK"
        proc = self._run_path(_join("to", "ken", " = ", sentinel))
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn(sentinel, proc.stdout + proc.stderr)
        self.assertIn("PS-FINDING-CONTENT", proc.stderr)
        self.assertIn("line=1", proc.stderr)
        self.assertIn("class=", proc.stderr)

    def test_tracked_and_path_no_message_fields(self) -> None:
        path_proc = self._run_path("clean content")
        self.assertEqual(path_proc.returncode, 0, path_proc.stderr)
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            subprocess.run([_git(), "init", "-q", str(repo)], check=True)
            self._git_run(repo, "config", "user.email", "t@t")
            self._git_run(repo, "config", "user.name", "t")
            (repo / "clean.txt").write_text("clean content\n", encoding="utf-8")
            self._git_run(repo, "add", "clean.txt")
            tracked_proc = subprocess.run(
                [sys.executable, str(CANONICAL_SCANNER)], cwd=repo,
                capture_output=True, text=True, encoding="utf-8",
            )
        self.assertEqual(tracked_proc.returncode, 0, tracked_proc.stderr)
        for output in (path_proc.stdout, tracked_proc.stdout):
            self.assertNotIn("commits=", output)
            self.assertNotIn("commit-set=", output)
            self.assertNotIn("messages=", output)


class TestPublicationSafetyScannerR2Contract(unittest.TestCase):
    """Durable R2 guards for lifecycle, multiplicity, and typed redaction."""

    def _module(self, suffix: str):
        return _load_canonical_scanner("_scanner_r2_" + suffix)

    def test_r2_async_reader_and_coverage_contract_exist(self) -> None:
        module = self._module("owners")
        required = (
            "ObjectReadSuccess",
            "CoverageProof",
            "_AsyncGitObjectReader",
            "ObjectReaderSession",
            "_build_coverage_proof",
        )
        missing = tuple(name for name in required if not hasattr(module, name))
        self.assertEqual(missing, (), "R2-OWNER-CONTRACT")

    def test_r2_coverage_proof_rejects_every_multiset_mutation(self) -> None:
        module = self._module("coverage")
        self.assertTrue(hasattr(module, "_build_coverage_proof"), "R2-COVERAGE-OWNER")
        if not hasattr(module, "_build_coverage_proof"):
            return
        expected = ("1" * 40, "2" * 40, "3" * 40)
        clean = module._build_coverage_proof(expected, expected, expected, expected)
        self.assertEqual(type(clean).__name__, "CoverageProof", "R2-COVERAGE-CLEAN")
        mutations = {
            "omission": expected[:-1],
            "duplicate": expected + (expected[-1],),
            "substitution": expected[:-1] + ("4" * 40,),
            "extra": expected + ("4" * 40,),
        }
        for axis in (1, 2, 3):
            for mutation, rows in mutations.items():
                values = [expected, expected, expected, expected]
                values[axis] = rows
                with self.subTest(axis=axis, mutation=mutation):
                    refusal = module._build_coverage_proof(*values)
                    self.assertEqual(refusal.failure_id, "PS-MSG-COVERAGE")
                    self.assertEqual(refusal.phase, "coverage")
                    self.assertEqual(refusal.reason, "multiplicity")

    def test_r2_refusal_schema_and_failure_registry_are_complete(self) -> None:
        module = self._module("failures")
        expected = {
            "PS-MSG-RANGE",
            "PS-MSG-READ",
            "PS-MSG-SPAWN",
            "PS-MSG-READ-TIMEOUT",
            "PS-MSG-REAP",
            "PS-MSG-FRAME",
            "PS-MSG-DECODE",
            "PS-MSG-LIMIT",
            "PS-MSG-COVERAGE",
            "PS-MSG-TIP-CHANGED",
        }
        self.assertTrue(hasattr(module, "_SCANNER_REFUSAL_IDS"), "R2-REFUSAL-REGISTRY")
        if not hasattr(module, "_SCANNER_REFUSAL_IDS"):
            return
        self.assertEqual(set(module._SCANNER_REFUSAL_IDS), expected)
        fields = tuple(module.Refusal.__dataclass_fields__)
        self.assertEqual(fields, ("failure_id", "phase", "reason"))
        self.assertNotIn("detail", fields)

    def test_r2_range_composition_root_is_async_and_finalization_aware(self) -> None:
        module = self._module("composition")
        self.assertTrue(hasattr(module, "_scan_range_async"), "R2-ASYNC-COMPOSITION")
        self.assertTrue(hasattr(module, "_finalize_range_outcome"), "R2-FINALIZER-PRECEDENCE")
        if not hasattr(module, "_scan_range_async"):
            return
        import inspect
        self.assertTrue(inspect.iscoroutinefunction(module._scan_range_async))
        outcome_fields = tuple(module.ScanOutcome.__dataclass_fields__)
        self.assertIn("reap_certificate", outcome_fields)
        self.assertIn("coverage", outcome_fields)

    def test_r2_reader_deadline_cancellation_and_reap_are_behavioral(self) -> None:
        module = self._module("reader_lifecycle")
        self.assertTrue(hasattr(module, "_AsyncGitObjectReader"), "R2-READER-LIFECYCLE")
        if not hasattr(module, "_AsyncGitObjectReader"):
            return

        oid = "1" * 40
        raw = b"tree " + b"2" * 40 + b"\n\nclean"
        helpers = {
            "header": "import sys,time; sys.stdin.buffer.readline(); time.sleep(60)",
            "body": (
                "import sys,time; o=sys.stdin.buffer.readline().strip(); "
                "sys.stdout.buffer.write(o+b' commit 10\\n'); sys.stdout.buffer.flush(); time.sleep(60)"
            ),
            "delimiter": (
                "import sys,time; o=sys.stdin.buffer.readline().strip(); "
                "sys.stdout.buffer.write(o+b' commit 10\\n'+b'x'*10); "
                "sys.stdout.buffer.flush(); time.sleep(60)"
            ),
        }

        async def finalize_until_terminal(reader, label: str) -> None:
            result = await reader.finalize()
            if result is not None:
                self.assertEqual(result.failure_id, "PS-MSG-REAP", label)
                self.assertEqual(reader.state, module.ReaderState.REAP_PENDING, label)
                result = await reader.finalize()
            self.assertIsNone(result, label)
            self.assertTrue(reader.reap_certificate.complete, label)

        async def timeout_row(label: str, body: str) -> None:
            reader = module._AsyncGitObjectReader(
                argv=(sys.executable, "-u", "-c", body),
                request_timeout=0.15,
                settle_timeout=0.25,
            )
            self.assertIsNone(await reader.start(), label)
            started = time.monotonic()
            refusal = await reader.read(oid, "commit")
            self.assertLess(time.monotonic() - started, 1.0, label)
            self.assertEqual(refusal.failure_id, "PS-MSG-READ-TIMEOUT", label)
            await finalize_until_terminal(reader, label)
            self.assertIsNotNone(reader.process.returncode, label)

        async def cancellation_row() -> None:
            reader = module._AsyncGitObjectReader(
                argv=(sys.executable, "-u", "-c", helpers["header"]),
                request_timeout=5.0,
                settle_timeout=0.25,
            )
            self.assertIsNone(await reader.start())
            task = asyncio.create_task(reader.read(oid, "commit"))
            await asyncio.sleep(0.05)
            task.cancel()
            refusal = await task
            self.assertEqual(refusal.failure_id, "PS-MSG-READ")
            self.assertEqual(refusal.reason, "cancelled")
            await finalize_until_terminal(reader, "cancelled")
            self.assertTrue(task.done())
            self.assertIsNotNone(reader.process.returncode)

        async def success_row() -> None:
            encoded = repr(raw)
            body = (
                "import sys; o=sys.stdin.buffer.readline().strip(); r=" + encoded + "; "
                "sys.stdout.buffer.write(o+b' commit '+str(len(r)).encode()+b'\\n'+r+b'\\n'); "
                "sys.stdout.buffer.flush()"
            )
            reader = module._AsyncGitObjectReader(
                argv=(sys.executable, "-u", "-c", body),
                request_timeout=1.0,
                settle_timeout=0.25,
            )
            self.assertIsNone(await reader.start())
            result = await reader.read(oid, "commit")
            self.assertEqual(type(result).__name__, "ObjectReadSuccess")
            self.assertEqual(result.raw, raw)
            await finalize_until_terminal(reader, "success")
            self.assertIsNotNone(reader.process.returncode)

        async def exercise() -> None:
            for label, body in helpers.items():
                with self.subTest(phase=label):
                    await timeout_row(label, body)
            await cancellation_row()
            await success_row()

        asyncio.run(exercise())

    def test_r2_composition_all_returns_finalize_once_and_cleanup_wins(self) -> None:
        module = self._module("all_returns")
        oid = "1" * 40
        other = "2" * 40
        clean_raw = b"tree " + other.encode("ascii") + b"\n\nclean"
        selection = module.RangeSelection(
            "origin", "refs/heads/main", oid, (oid,), ()
        )
        originals = (
            module._range_selection,
            module._tip_blob_ids,
            module._build_coverage_proof,
        )

        def complete_certificate(identity: str = "fixture"):
            tick = asyncio.get_running_loop().time()
            child = module.ChildObservation(identity, 0, True, tick)
            stdin = module.TransportObservation("owned", "input-closed", True, None, tick)
            stdout = module.TransportObservation("owned", "output-eof", True, None, tick)
            finalizer = module.FinalizerObservation("fixture-task", True, False, False, tick)
            return module.ReaderReapCertificate(
                "fixture-session", 1, identity, "fixture-task", child, stdin, stdout,
                finalizer, (), tick + 1e-6, module.ReaderState.REAPED,
            )

        class FakeReader:
            def __init__(self, row: str) -> None:
                self.row = row
                self.finalize_calls = 0
                self.reap_certificate = None
                self.state = module.ReaderState.ACTIVE

            async def start(self):
                if self.row == "start-exception":
                    raise RuntimeError("synthetic")
                if self.row == "start-refusal":
                    return module._refusal("PS-MSG-READ", "spawn")
                return None

            async def read(self, requested: str, object_type: str):
                if self.row == "read-exception":
                    raise RuntimeError("synthetic")
                if self.row == "read-refusal":
                    return module._refusal("PS-MSG-READ", "short-read")
                raw = b"invalid" if self.row == "decode-refusal" else clean_raw
                returned = other if self.row == "coverage-refusal" else requested
                return module.ObjectReadSuccess(requested, returned, object_type, raw)

            async def finalize(self):
                self.finalize_calls += 1
                if self.row == "cleanup-refusal":
                    self.state = module.ReaderState.REAP_PENDING
                    return module._refusal("PS-MSG-REAP", "unreaped")
                self.reap_certificate = complete_certificate()
                self.state = module.ReaderState.REAPED
                return None

        async def exercise() -> None:
            module._range_selection = lambda _remote, _destination: selection
            module._tip_blob_ids = lambda _selection: {}
            rows = {
                "start-exception": "PS-MSG-READ",
                "start-refusal": "PS-MSG-READ",
                "read-exception": "PS-MSG-READ",
                "read-refusal": "PS-MSG-READ",
                "decode-refusal": "PS-MSG-FRAME",
                "coverage-refusal": "PS-MSG-COVERAGE",
                "tip-drift": "PS-MSG-TIP-CHANGED",
            }
            for row, expected_failure in rows.items():
                with self.subTest(row=row):
                    reader = FakeReader(row)
                    resolver = (lambda: other) if row == "tip-drift" else (lambda: oid)
                    outcome = await module._scan_range_async(
                        "origin", "refs/heads/main", lambda _line: [],
                        head_resolver=resolver,
                        reader_factory=lambda: reader,
                    )
                    self.assertEqual(outcome.kind, "refusal")
                    self.assertEqual(outcome.refusal.failure_id, expected_failure)
                    self.assertTrue(outcome.reap_certificate.complete)
                    self.assertEqual(reader.finalize_calls, 1)

            for row, finder, expected_kind in (
                ("clean", lambda _line: [], "clean"),
                ("finding", lambda _line: ["synthetic"], "findings"),
            ):
                with self.subTest(row=row):
                    reader = FakeReader(row)
                    outcome = await module._scan_range_async(
                        "origin", "refs/heads/main", finder,
                        head_resolver=lambda: oid,
                        reader_factory=lambda: reader,
                    )
                    self.assertEqual(outcome.kind, expected_kind)
                    self.assertTrue(outcome.reap_certificate.complete)
                    self.assertEqual(reader.finalize_calls, 1)

            reader = FakeReader("cleanup-refusal")
            outcome = await module._scan_range_async(
                "origin", "refs/heads/main", lambda _line: [],
                head_resolver=lambda: oid,
                reader_factory=lambda: reader,
            )
            self.assertEqual(outcome.kind, "refusal")
            self.assertEqual(outcome.refusal.failure_id, "PS-MSG-REAP")
            self.assertIsNone(outcome.reap_certificate)
            self.assertEqual(reader.finalize_calls, 2)

        try:
            asyncio.run(exercise())
        finally:
            (
                module._range_selection,
                module._tip_blob_ids,
                module._build_coverage_proof,
            ) = originals


class TestPublicationSafetyScannerR3Contract(unittest.TestCase):
    """R3 RED/GREEN guards for cancellation, live coverage, and redaction."""

    def _module(self, suffix: str):
        return _load_canonical_scanner("_scanner_r3_" + suffix)

    def test_r3_cancel_during_finalize_retries_until_reaped(self) -> None:
        module = self._module("cancel_finalize")

        async def exercise() -> None:
            reader = module._AsyncGitObjectReader(
                argv=(sys.executable, "-u", "-c", "import time; time.sleep(60)"),
                request_timeout=1.0,
                settle_timeout=0.2,
            )
            self.assertIsNone(await reader.start())
            process = reader.process
            self.assertIsNotNone(process)
            try:
                task = asyncio.create_task(module._finalize_reader(reader))
                await asyncio.sleep(0.05)
                task.cancel()
                first = await task
                self.assertIsNotNone(first)
                self.assertEqual(first.failure_id, "PS-MSG-READ")
                self.assertEqual(first.reason, "cancelled")
                retry = await reader.finalize()
                if retry is not None and retry.failure_id == "PS-MSG-REAP":
                    retry = await reader.finalize()
                self.assertIsNone(retry, "R3-CANCEL-RETRY-FAILED")
                self.assertIsNotNone(process.returncode, "R3-CANCEL-LEFT-CHILD-LIVE")
                self.assertTrue(reader.is_finalized)
                self.assertEqual(reader.state.name, "REAPED")
                certificate = reader.reap_certificate
                self.assertIsNotNone(certificate)
                self.assertTrue(certificate.complete)
            finally:
                if process.returncode is None:
                    process.kill()
                    await process.wait()

        asyncio.run(exercise())

    def test_r3_live_reader_detector_oid_multiplicity(self) -> None:
        module = self._module("live_coverage")
        self.assertTrue(hasattr(module, "CoverageRecorder"), "R3-LIVE-COVERAGE-OWNER")
        self.assertTrue(hasattr(module, "CoverageEvent"), "R3-LIVE-COVERAGE-EVENT")
        signature = inspect.signature(module._scan_range_async)
        self.assertIn("coverage_observer", signature.parameters, "R3-LIVE-COVERAGE-SEAM")

        oid = "1" * 40
        selection = module.RangeSelection(
            "origin", "refs/heads/main", "2" * 40, (oid,), ()
        )

        class Reader:
            def __init__(self, returned_oid=oid):
                self.returned_oid = returned_oid
                self.reap_certificate = None
                self.state = module.ReaderState.ACTIVE

            async def start(self):
                return None

            async def read(self, requested_oid, expected_type):
                raw = b"tree " + b"3" * 40 + b"\n\nclean message"
                return module.ObjectReadSuccess(
                    requested_oid, self.returned_oid, expected_type, raw
                )

            async def finalize(self):
                tick = asyncio.get_running_loop().time()
                child = module.ChildObservation("fixture", 0, True, tick)
                stdin = module.TransportObservation("owned", "input-closed", True, None, tick)
                stdout = module.TransportObservation("owned", "output-eof", True, None, tick)
                finalizer = module.FinalizerObservation("fixture-task", True, False, False, tick)
                self.reap_certificate = module.ReaderReapCertificate(
                    "fixture-session", 1, "fixture", "fixture-task", child,
                    stdin, stdout, finalizer, (), tick + 1e-6,
                    module.ReaderState.REAPED,
                )
                self.state = module.ReaderState.REAPED
                return None

        originals = (
            module._range_selection,
            module._tip_blob_ids,
            module._confirm_tip,
            module._content_hits,
        )

        async def run_case(*, returned_oid=oid, expected=(oid,), detector_fault=False):
            module._range_selection = lambda *_args: module.RangeSelection(
                selection.remote,
                selection.destination,
                selection.tip,
                expected,
                selection.changed_paths,
            )
            module._tip_blob_ids = lambda _selection: {}
            module._confirm_tip = lambda *_args: None
            if detector_fault:
                module._content_hits = lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    RuntimeError("synthetic-detector-fault")
                )
            else:
                module._content_hits = lambda *_args, **_kwargs: []
            events = []
            return await module._scan_range_async(
                "origin", "refs/heads/main", lambda _line: [],
                reader_factory=lambda: Reader(returned_oid),
                coverage_observer=lambda event, value: events.append((event, value)),
            ), events

        try:
            clean, events = asyncio.run(run_case())
            self.assertEqual(clean.kind, "clean")
            self.assertEqual(clean.coverage.expected_count, 1)
            self.assertEqual(clean.coverage.requested_count, 1)
            self.assertEqual(clean.coverage.acquired_count, 1)
            self.assertEqual(clean.coverage.scanned_count, 1)
            self.assertEqual(
                [event for event, _value in events],
                [
                    module.CoverageEvent.REQUESTED,
                    module.CoverageEvent.ACQUIRED,
                    module.CoverageEvent.SCANNED,
                ],
            )
            wrong, _ = asyncio.run(run_case(returned_oid="4" * 40))
            self.assertEqual(wrong.refusal.failure_id, "PS-MSG-COVERAGE")
            duplicate, _ = asyncio.run(run_case(expected=(oid, oid)))
            self.assertEqual(duplicate.refusal.failure_id, "PS-MSG-COVERAGE")
            detector, _ = asyncio.run(run_case(detector_fault=True))
            self.assertEqual(detector.kind, "refusal")
            self.assertNotEqual(detector.kind, "clean")
            self.assertNotEqual(
                module._commit_set_digest((oid, "4" * 40)),
                module._commit_set_digest(("4" * 40, oid)),
            )
        finally:
            (
                module._range_selection,
                module._tip_blob_ids,
                module._confirm_tip,
                module._content_hits,
            ) = originals

    def test_r3_scanner_formatter_redacts_every_sensitive_subject(self) -> None:
        module = self._module("redaction")
        self.assertTrue(hasattr(module, "_format_outcome"), "R3-SCANNER-FORMATTER")
        if not hasattr(module, "_format_outcome"):
            return
        sentinels = {
            "staged": "SENTINEL_STAGE_VALUE",
            "path": "SENTINEL_PATH_VALUE",
            "tip": "SENTINEL_TIP_VALUE",
            "subject": "SENTINEL_MESSAGE_SUBJECT",
            "body": "SENTINEL_MESSAGE_BODY",
            "trailer": "SENTINEL_MESSAGE_TRAILER",
            "machine": _join(WIN, BS, USERS, BS, "sentinel-user"),
            "exception": "SENTINEL_EXCEPTION_TEXT",
        }
        for label, sentinel in sentinels.items():
            finding = module.Finding(
                "PS-FINDING-CONTENT", "path-blob", sentinel, 7, "value-token"
            )
            outcome = module.ScanOutcome("findings", "path", findings=(finding,))
            rendered = module._format_outcome(outcome)
            self.assertIsInstance(rendered, tuple)
            combined = "\n".join(str(value) for value in rendered)
            with self.subTest(subject=label, channel="formatter"):
                self.assertNotIn(sentinel, combined, "R3-REDACTION-SENTINEL")

            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                module._emit_outcome(outcome)
            channels = stdout.getvalue() + stderr.getvalue()
            with self.subTest(subject=label, channel="runtime"):
                self.assertNotIn(sentinel, channels, "R3-REDACTION-RUNTIME")


class TestPublicationSafetyScannerR4Contract(unittest.TestCase):
    """R4 guards for observed settlement and live proof boundaries."""

    def _module(self, suffix: str):
        return _load_canonical_scanner("_scanner_r4_" + suffix)

    def test_r4_certificate_contains_only_observed_owned_participants(self) -> None:
        module = self._module("certificate")
        self.assertTrue(hasattr(module, "ReaderReapCertificate"), "R4-READER-CERTIFICATE")
        certificate_type = module.ReaderReapCertificate
        self.assertFalse(
            {"writer_task_joined", "reader_task_joined", "child_reaped"}
            & {field.name for field in dataclasses.fields(certificate_type)},
            "R4-FABRICATED-CERTIFICATE-FIELDS",
        )
        child = module.ChildObservation("child-1", 0, True, 2.0)
        stdin = module.TransportObservation("owned", "input-closed", True, None, 2.1)
        stdout = module.TransportObservation("owned", "output-eof", True, None, 2.2)
        finalizer = module.FinalizerObservation("task-1", True, False, False, 2.3)
        certificate = certificate_type(
            "session-1", 1, "child-1", "task-1", child, stdin, stdout,
            finalizer, (), 2.4, module.ReaderState.REAPED,
        )
        self.assertTrue(certificate.complete)
        mutations = (
            dataclasses.replace(certificate, attempts_used=3),
            dataclasses.replace(certificate, owned_child_identity="child-2"),
            dataclasses.replace(certificate, child=dataclasses.replace(child, terminal_observed=False)),
            dataclasses.replace(certificate, stdin=dataclasses.replace(stdin, observed=False)),
            dataclasses.replace(certificate, stdout=dataclasses.replace(stdout, terminal_fact="unobserved")),
            dataclasses.replace(certificate, finalizer=dataclasses.replace(finalizer, completion_observed=False)),
            dataclasses.replace(certificate, verified_at_monotonic_tick=2.0),
            dataclasses.replace(certificate, terminal_state=module.ReaderState.REAP_PENDING),
        )
        for index, mutated in enumerate(mutations):
            with self.subTest(index=index):
                self.assertFalse(mutated.complete, "R4-CERTIFICATE-MUTATION-ACCEPTED")

    def test_r4_reader_uses_one_three_second_budget_and_two_entries(self) -> None:
        module = self._module("deadline")
        self.assertEqual(module.OBJECT_REAP_ATTEMPT_SECONDS, 3.0)
        self.assertEqual(module.OBJECT_REAP_MAX_ATTEMPTS, 2)

        async def exercise() -> None:
            reader = module.ObjectReaderSession(
                argv=(sys.executable, "-u", "-c", "import time; time.sleep(60)"),
                request_timeout=1.0,
                settle_timeout=0.2,
            )
            self.assertIsNone(await reader.start())
            process = reader.process
            self.assertIsNotNone(process)
            try:
                finalization = await reader.finalize()
                if finalization is not None and finalization.failure_id == "PS-MSG-REAP":
                    finalization = await reader.finalize()
                self.assertIsNone(finalization)
                certificate = reader.reap_certificate
                self.assertIsNotNone(certificate)
                self.assertTrue(certificate.complete)
                self.assertLessEqual(certificate.attempts_used, 2)
                self.assertIsNotNone(process.returncode)
            finally:
                if process.returncode is None:
                    process.kill()
                    await process.wait()

        asyncio.run(exercise())

    def test_r4_live_coverage_fault_port_drives_emitter(self) -> None:
        module = self._module("coverage")
        signature = inspect.signature(module._scan_range_async)
        self.assertIn("coverage_fault", signature.parameters, "R4-COVERAGE-FAULT-SEAM")
        self.assertTrue(hasattr(module, "CoverageFaultPort"), "R4-COVERAGE-FAULT-PORT")

        first, second = "1" * 40, "2" * 40
        expected = (first, second)

        class Reader:
            def __init__(self):
                self.reap_certificate = None
                self.state = module.ReaderState.ACTIVE

            async def start(self):
                return None

            async def read(self, requested_oid, expected_type):
                raw = b"tree " + b"3" * 40 + b"\n\nclean message"
                return module.ObjectReadSuccess(
                    requested_oid, requested_oid, expected_type, raw
                )

            async def finalize(self):
                tick = asyncio.get_running_loop().time()
                child = module.ChildObservation("fixture", 0, True, tick)
                stdin = module.TransportObservation("owned", "input-closed", True, None, tick)
                stdout = module.TransportObservation("owned", "output-eof", True, None, tick)
                finalizer = module.FinalizerObservation("fixture-task", True, False, False, tick)
                self.reap_certificate = module.ReaderReapCertificate(
                    "fixture-session", 1, "fixture", "fixture-task", child,
                    stdin, stdout, finalizer, (), tick + 1e-6,
                    module.ReaderState.REAPED,
                )
                self.state = module.ReaderState.REAPED
                return None

        originals = (
            module._range_selection, module._tip_blob_ids,
            module._confirm_tip, module._content_hits,
        )
        module._range_selection = lambda *_args: module.RangeSelection(
            "origin", "refs/heads/main", "4" * 40, expected, ()
        )
        module._tip_blob_ids = lambda _selection: {}
        module._confirm_tip = lambda *_args: None
        module._content_hits = lambda *_args, **_kwargs: []

        def run(transform, selection_oids=expected):
            module._range_selection = lambda *_args: module.RangeSelection(
                "origin", "refs/heads/main", "4" * 40, selection_oids, ()
            )
            outcome = asyncio.run(module._scan_range_async(
                "origin", "refs/heads/main", lambda _line: [],
                reader_factory=Reader,
                coverage_fault=module.CoverageFaultPort(transform),
            ))
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = module._emit_outcome(outcome)
            return outcome, code, stdout.getvalue(), stderr.getvalue()

        mutations = {
            "omit-requested": lambda event, oid: () if (
                event is module.CoverageEvent.REQUESTED and oid == first
            ) else ((event, oid),),
            "omit-acquired": lambda event, oid: () if (
                event is module.CoverageEvent.ACQUIRED and oid == first
            ) else ((event, oid),),
            "omit-scanned": lambda event, oid: () if (
                event is module.CoverageEvent.SCANNED and oid == first
            ) else ((event, oid),),
            "duplicate": lambda event, oid: ((event, oid), (event, oid)) if (
                event is module.CoverageEvent.ACQUIRED and oid == first
            ) else ((event, oid),),
            "substitute": lambda event, oid: ((event, "5" * 40),) if (
                event is module.CoverageEvent.SCANNED and oid == first
            ) else ((event, oid),),
            "extra": lambda event, oid: ((event, oid), (event, "6" * 40)) if (
                event is module.CoverageEvent.REQUESTED and oid == first
            ) else ((event, oid),),
        }
        try:
            for row, transform in mutations.items():
                outcome, code, stdout, stderr = run(transform)
                with self.subTest(row=row):
                    self.assertEqual(outcome.refusal.failure_id, "PS-MSG-COVERAGE")
                    self.assertEqual(code, 2)
                    self.assertNotIn("receipt=v2", stdout + stderr)

            duplicate_input, code, stdout, stderr = run(
                lambda event, oid: ((event, oid),), (first, first)
            )
            self.assertEqual(duplicate_input.refusal.failure_id, "PS-MSG-COVERAGE")
            self.assertEqual(code, 2)
            self.assertNotIn("receipt=v2", stdout + stderr)

            deferred = []
            def reorder(event, oid):
                if event is not module.CoverageEvent.SCANNED:
                    return ((event, oid),)
                deferred.append(oid)
                if len(deferred) == 1:
                    return ()
                return ((event, deferred[1]), (event, deferred[0]))

            reordered, code, stdout, stderr = run(reorder)
            independently_observed = (second, first)
            independent_digest = hashlib.sha256(
                b"publication-safety-range-receipt-v2"
                + b"\0" + b"\0".join(oid.encode("ascii") for oid in independently_observed)
            ).hexdigest()
            self.assertEqual(reordered.coverage.scanned_message_oids, independently_observed)
            self.assertEqual(code, 0)
            self.assertIn("commit-set=" + independent_digest, stdout)
            self.assertEqual(stderr, "")

            clean, code, stdout, stderr = run(lambda event, oid: ((event, oid),))
            self.assertEqual(clean.kind, "clean")
            self.assertEqual(clean.coverage.scanned_message_oids, expected)
            self.assertEqual(code, 0)
            self.assertIn("receipt=v2", stdout)
            self.assertEqual(stderr, "")
        finally:
            (
                module._range_selection, module._tip_blob_ids,
                module._confirm_tip, module._content_hits,
            ) = originals

    def test_r4_actual_boundary_redaction_matrix(self) -> None:
        module = self._module("redaction")
        sentinels = {
            "staged": "R4_STAGE_SENTINEL",
            "path": "R4_PATH_SENTINEL",
            "tip": "R4_TIP_SENTINEL",
            "subject": "R4_SUBJECT_SENTINEL",
            "body": "R4_BODY_SENTINEL",
            "trailer": "R4_TRAILER_SENTINEL",
            "machine": _join(WIN, BS, USERS, BS, "r4-sentinel-user"),
        }
        subjects = {
            "staged": "tracked-blob", "path": "path-blob", "tip": "tip-blob",
            "subject": "commit-message", "body": "commit-message",
            "trailer": "commit-message", "machine": "path-blob",
        }
        for row, sentinel in sentinels.items():
            outcome = module.ScanOutcome(
                "findings", "range" if subjects[row] == "commit-message" else "path",
                findings=(module.Finding(
                    "PS-FINDING-COMMIT-MESSAGE" if subjects[row] == "commit-message" else "PS-FINDING-CONTENT",
                    subjects[row], sentinel, 1, "value-token",
                ),),
            )
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                module._emit_outcome(outcome)
            with self.subTest(row=row):
                self.assertNotIn(sentinel, stdout.getvalue() + stderr.getvalue(), f"R4-REDACTION:{row}")


class TestPublicationSafetyScannerR5Proof(unittest.TestCase):
    """Proof-only inventory for the four architecture R4 enforcement gaps."""

    def test_r5_proof_inventory(self) -> None:
        required = {
            "test_r5_reader_retry_and_certificate_mutation_matrix",
            "test_r5_live_counter_detector_skip_and_producer_redaction_matrix",
        }
        self.assertEqual(required - set(dir(self.__class__)), set(), "R5-MISSING-PROBE")

    def _module(self, suffix: str):
        return _load_canonical_scanner("_scanner_r5_" + suffix)

    def test_r5_reader_retry_and_certificate_mutation_matrix(self) -> None:
        module = self._module("reader_retry")

        async def exercise() -> None:
            reader = module.ObjectReaderSession(settle_timeout=0.01)
            reader._state = module.ReaderState.ACTIVE
            tick = asyncio.get_running_loop().time()
            first = module._ReaderFinalizerResult(
                module._refusal("PS-MSG-REAP", "unreaped"),
                module.ChildObservation("owned-child", None, False, tick),
                module.TransportObservation(
                    "owned", "input-closed", True, None, tick + 0.01
                ),
                module.TransportObservation(
                    "owned", "unobserved", False, "stdout-drain", tick + 0.02
                ),
                ("stdout-drain",),
            )
            second = module._ReaderFinalizerResult(
                None,
                module.ChildObservation("owned-child", 0, True, tick + 0.03),
                module.TransportObservation(
                    "owned", "input-closed", True, None, tick + 0.04
                ),
                module.TransportObservation(
                    "owned", "output-eof", True, None, tick + 0.05
                ),
                (),
            )
            rows = iter((first, second))

            async def drive():
                reader._attempts_used += 1
                reader._state = module.ReaderState.FINALIZING
                return next(rows)

            with mock.patch.object(
                reader, "_drive_finalizer", side_effect=drive
            ) as finalizer:
                refusal = await reader.finalize()
                self.assertEqual(refusal.failure_id, "PS-MSG-REAP")
                self.assertEqual(reader.state, module.ReaderState.REAP_PENDING)
                self.assertIsNone(reader.reap_certificate)

                self.assertIsNone(await reader.finalize())
                self.assertEqual(reader.state, module.ReaderState.REAPED)
                certificate = reader.reap_certificate
                self.assertIsNotNone(certificate)
                self.assertTrue(certificate.complete)
                self.assertEqual(certificate.attempts_used, 2)
                self.assertEqual(finalizer.call_count, 2)

                stable = reader.reap_certificate
                self.assertIsNone(await reader.finalize())
                self.assertIs(reader.reap_certificate, stable)
                self.assertEqual(finalizer.call_count, 2, "R5-REAPED-REENTERED")

            certificate = reader.reap_certificate
            mutations = {
                "attempt-zero": dataclasses.replace(certificate, attempts_used=0),
                "attempt-overflow": dataclasses.replace(certificate, attempts_used=3),
                "owned-child": dataclasses.replace(
                    certificate, owned_child_identity="other-child"
                ),
                "child-return": dataclasses.replace(
                    certificate,
                    child=dataclasses.replace(certificate.child, return_code=None),
                ),
                "child-terminal": dataclasses.replace(
                    certificate,
                    child=dataclasses.replace(
                        certificate.child, terminal_observed=False
                    ),
                ),
                "stdin-owner": dataclasses.replace(
                    certificate,
                    stdin=dataclasses.replace(certificate.stdin, ownership="not-owned"),
                ),
                "stdin-fact": dataclasses.replace(
                    certificate,
                    stdin=dataclasses.replace(certificate.stdin, terminal_fact="unobserved"),
                ),
                "stdin-observed": dataclasses.replace(
                    certificate,
                    stdin=dataclasses.replace(certificate.stdin, observed=False),
                ),
                "stdout-owner": dataclasses.replace(
                    certificate,
                    stdout=dataclasses.replace(certificate.stdout, ownership="not-owned"),
                ),
                "stdout-fact": dataclasses.replace(
                    certificate,
                    stdout=dataclasses.replace(certificate.stdout, terminal_fact="unobserved"),
                ),
                "stdout-observed": dataclasses.replace(
                    certificate,
                    stdout=dataclasses.replace(certificate.stdout, observed=False),
                ),
                "owned-finalizer": dataclasses.replace(
                    certificate, owned_finalizer_identity="other-task"
                ),
                "finalizer-complete": dataclasses.replace(
                    certificate,
                    finalizer=dataclasses.replace(
                        certificate.finalizer, completion_observed=False
                    ),
                ),
                "finalizer-cancel": dataclasses.replace(
                    certificate,
                    finalizer=dataclasses.replace(certificate.finalizer, cancelled=True),
                ),
                "finalizer-error": dataclasses.replace(
                    certificate,
                    finalizer=dataclasses.replace(
                        certificate.finalizer, exception_observed=True
                    ),
                ),
                "verification-order": dataclasses.replace(
                    certificate,
                    verified_at_monotonic_tick=max(
                        certificate.child.observed_at_monotonic_tick,
                        certificate.stdin.observed_at_monotonic_tick,
                        certificate.stdout.observed_at_monotonic_tick,
                        certificate.finalizer.observed_at_monotonic_tick,
                    ),
                ),
                "terminal-state": dataclasses.replace(
                    certificate, terminal_state=module.ReaderState.REAP_PENDING
                ),
            }
            for name, mutated in mutations.items():
                with self.subTest(participant=name):
                    self.assertFalse(mutated.complete, "R5-READER-CERTIFICATE-ACCEPTED")

        asyncio.run(exercise())

    def test_r5_live_counter_detector_skip_and_producer_redaction_matrix(self) -> None:
        module = self._module("coverage_redaction")
        oid = "1" * 40
        selection = module.RangeSelection(
            "origin", "refs/heads/main", "2" * 40, (oid,), ()
        )

        class Reader:
            def __init__(self):
                self.reap_certificate = None
                self.state = module.ReaderState.ACTIVE

            async def start(self):
                return None

            async def read(self, requested_oid, expected_type):
                raw = b"tree " + b"3" * 40 + b"\n\nclean message"
                return module.ObjectReadSuccess(
                    requested_oid, requested_oid, expected_type, raw
                )

            async def finalize(self):
                tick = asyncio.get_running_loop().time()
                child = module.ChildObservation("fixture", 0, True, tick)
                stdin = module.TransportObservation(
                    "owned", "input-closed", True, None, tick
                )
                stdout = module.TransportObservation(
                    "owned", "output-eof", True, None, tick
                )
                finalizer = module.FinalizerObservation(
                    "fixture-task", True, False, False, tick
                )
                self.reap_certificate = module.ReaderReapCertificate(
                    "fixture-session", 1, "fixture", "fixture-task", child,
                    stdin, stdout, finalizer, (), tick + 1e-6,
                    module.ReaderState.REAPED,
                )
                self.state = module.ReaderState.REAPED
                return None

        originals = (
            module._range_selection,
            module._tip_blob_ids,
            module._confirm_tip,
            module._content_hits,
        )
        module._range_selection = lambda *_args: selection
        module._tip_blob_ids = lambda _selection: {}
        module._confirm_tip = lambda *_args: None

        async def run(*, detector_completes: bool):
            state = {"complete": False}
            events = []

            def detector(*_args, **_kwargs):
                state["complete"] = detector_completes
                return []

            def observer(event, value):
                if event is module.CoverageEvent.SCANNED and not state["complete"]:
                    raise RuntimeError("R5-DETECTOR-SKIPPED")
                events.append((event, value))

            module._content_hits = detector
            outcome = await module._scan_range_async(
                "origin", "refs/heads/main", lambda _line: [],
                reader_factory=Reader,
                coverage_observer=observer,
            )
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = module._emit_outcome(outcome)
            return outcome, events, code, stdout.getvalue() + stderr.getvalue()

        try:
            with mock.patch.object(module, "Counter", wraps=module.Counter) as counter:
                clean, events, code, output = asyncio.run(
                    run(detector_completes=True)
                )
            self.assertEqual(clean.kind, "clean")
            self.assertEqual(code, 0)
            self.assertIn("receipt=v2", output)
            self.assertGreaterEqual(counter.call_count, 5, "R5-LIVE-COUNTER-BYPASSED")
            self.assertEqual(
                [event for event, _value in events],
                [
                    module.CoverageEvent.REQUESTED,
                    module.CoverageEvent.ACQUIRED,
                    module.CoverageEvent.SCANNED,
                ],
            )

            skipped, _events, code, output = asyncio.run(
                run(detector_completes=False)
            )
            self.assertEqual(skipped.kind, "refusal")
            self.assertEqual(code, 2)
            self.assertNotIn("receipt=v2", output)

            module._content_hits = originals[3]

            body_sentinel = _join("R5_BODY_", "123456789")
            path_sentinel = _join("R5_PATH_", "123456789", ".txt")
            machine_sentinel = _join("R5_MACHINE_", "123456789")
            secret_line = _join(
                "to", "ken", " = ", '"', body_sentinel, '"'
            )
            producer_rows = {
                "message-body": module._content_hits(
                    secret_line, oid, lambda _line: [],
                    subject_kind="commit-message",
                ),
                "path-locator": module._content_hits(
                    secret_line, path_sentinel, lambda _line: [],
                    subject_kind="path-blob",
                ),
                "machine-classifier": module._content_hits(
                    "ordinary line", path_sentinel,
                    lambda _line: [machine_sentinel],
                    subject_kind="tip-blob",
                ),
            }
            scratch = REPO_ROOT / ".scratch"
            scratch.mkdir(exist_ok=True)
            for label, findings in producer_rows.items():
                self.assertTrue(findings, "R5-PRODUCER-DID-NOT-FIRE")
                outcome = module.ScanOutcome(
                    "findings", "range", findings=tuple(findings)
                )
                stdout, stderr = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    self.assertEqual(module._emit_outcome(outcome), 1)
                combined = stdout.getvalue() + stderr.getvalue()
                with tempfile.TemporaryDirectory(
                    prefix="r5-redaction-", dir=scratch
                ) as temp_dir:
                    persisted = Path(temp_dir) / "evidence.txt"
                    persisted.write_text(combined, encoding="utf-8")
                    channels = {
                        "stdout": stdout.getvalue(),
                        "stderr": stderr.getvalue(),
                        "assertion": f"row={label};output={combined}",
                        "persisted": persisted.read_text(encoding="utf-8"),
                    }
                for sentinel in (
                    body_sentinel, path_sentinel, machine_sentinel
                ):
                    for channel, rendered in channels.items():
                        with self.subTest(row=label, channel=channel):
                            self.assertNotIn(sentinel, rendered)
        finally:
            (
                module._range_selection,
                module._tip_blob_ids,
                module._confirm_tip,
                module._content_hits,
            ) = originals


class TestThisTestFileIsGateSafe(unittest.TestCase):
    """MF6: assert this very test file contains no machine-local-path literal the
    scanner would flag, so staging it never self-trips the publication gate."""

    def test_no_flaggable_literal_in_this_source(self) -> None:
        find_machine_paths = _load_find_machine_paths()
        src = Path(__file__).read_text(encoding="utf-8")
        offenders = []
        for n, line in enumerate(src.splitlines(), start=1):
            hits = find_machine_paths(line)
            if hits:
                offenders.append((n, hits, line.strip()[:80]))
        self.assertEqual(offenders, [], f"flaggable literals in test source: {offenders}")


if __name__ == "__main__":
    unittest.main()
