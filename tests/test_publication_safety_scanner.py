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
import ctypes
import dataclasses
import importlib.util
import hashlib
import inspect
import io
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
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


def _linux_child_subreaper_state() -> int:
    libc = ctypes.CDLL(None, use_errno=True)
    state = ctypes.c_int()
    if libc.prctl(37, ctypes.byref(state), 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "PR_GET_CHILD_SUBREAPER")
    return state.value


def _set_linux_child_subreaper_state(value: int) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, value, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "PR_SET_CHILD_SUBREAPER")


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


def _empty_history_proof(module, selection):
    object_ids = tuple(sorted(selection.object_oids))
    return module.HistoryProof(
        selection.expected_oids,
        object_ids,
        (),
        0,
        0,
        0,
        (),
        (),
        module._commit_set_digest(selection.expected_oids),
        module._oid_set_digest(b"object-set", object_ids),
        module._oid_set_digest(b"blob-set", ()),
        module._subject_set_digest(()),
        module._path_set_digest(()),
    )


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
                        filename="scripts/universal-hooks/scripts/check-publication-safety.py",
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
                        filename="scripts/universal-hooks/scripts/check-publication-safety.py",
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
                        filename="scripts/universal-hooks/scripts/check-publication-safety.py",
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
                            filename="scripts/universal-hooks/scripts/check-publication-safety.py",
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
                    self._run_cached(
                        scanner, content,
                        filename="scripts/universal-hooks/scripts/check-publication-safety.py",
                    ),
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
    (`<tip> --not <authoritative-push-destination-oid>`, or all history for
    a missing destination), read from COMMITTED objects at `tip` -- never the
    working tree or index -- rather than the staged index `tracked` mode
    reads. See that scanner's own `--range` branch for the implementation."""

    def _init_range_repo(self, td: Path) -> Path:
        """git-init a bare 'origin.git' and a working 'repo' next to it,
        wire 'repo' to 'origin' as remote `origin`, and publish one
        throwaway seed commit so `--range origin main` has a real remote
        tracking ref to diff against. Returns the working repo path."""
        git = _git()
        origin = td / "origin.git"
        repo = td / "repo"
        subprocess.run([git, "init", "-q", "--bare", str(origin)], check=True, capture_output=True)
        subprocess.run(
            [git, "init", "-q", "-b", "claude", str(repo)],
            check=True,
            capture_output=True,
        )
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
        subprocess.run(
            [git, "-C", str(repo), "branch", "main", "HEAD"],
            check=True,
            capture_output=True,
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
                    expected_blob_bytes = sum(
                        len((repo / name).read_bytes()) for name in ("seed.txt", "b.txt")
                    )
                    git = _git()
                    tip = subprocess.run(
                        [git, "-C", str(repo), "rev-parse", "HEAD"],
                        check=True, capture_output=True, text=True,
                    ).stdout.strip()
                    rc, out, err = self._run_range(scanner, repo, "origin", "claude")
                    self.assertEqual(rc, 0, err)
                    self.assertRegex(
                        out,
                        rf"^publication-safety: clean \(range, receipt=v3, commits=2, "
                        rf"commit-set=[0-9a-f]{{64}}, messages=complete, objects=6, "
                        rf"object-set=[0-9a-f]{{64}}, blobs=2, blob-set=[0-9a-f]{{64}}, "
                        rf"blob-bytes={expected_blob_bytes}, text=2, binary=0, subjects=3, "
                        rf"subject-set=[0-9a-f]{{64}}, paths=2, path-set=[0-9a-f]{{64}}, "
                        rf"history=complete, remote=origin, dst=claude, "
                        rf"src=claude, tip={tip}\)\n?$",
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

    def test_range_mode_add_then_delete_secret_blocks(self) -> None:
        # Complete-history coverage: unpublished content remains publication
        # input even when a later unpublished commit deletes its final path.
        leak = "pass" + "word" + ": hunter2"
        for scanner in SCANNERS:
            with self.subTest(scanner=scanner.parent.parent.name):
                with tempfile.TemporaryDirectory() as td:
                    repo = self._init_range_repo(Path(td))
                    self._commit_file(repo, "gone.txt", leak)
                    self._rm_file(repo, "gone.txt")
                    rc, out, err = self._run_range(scanner, repo, "origin", "claude")
                    self.assertEqual(rc, 1, out + err)
                    self.assertEqual(out, "")
                    self.assertIn("PS-FINDING-CONTENT", err)
                    self.assertNotIn(leak, err)

    def test_range_mode_sanitized_tip_still_blocks_historical_secret(self) -> None:
        leak = "pass" + "word" + ": hunter2"
        with tempfile.TemporaryDirectory() as td:
            repo = self._init_range_repo(Path(td))
            self._commit_file(repo, "history.txt", leak, message="unsafe history")
            self._commit_file(repo, "history.txt", "clean replacement", message="sanitize tip")
            rc, out, err = self._run_range(CANONICAL_SCANNER, repo, "origin", "claude")
            self.assertEqual(rc, 1, out + err)
            self.assertIn("PS-FINDING-CONTENT", err)
            self.assertNotIn(leak, err)

    def test_range_mode_rename_maps_historical_blob_to_both_paths(self) -> None:
        leak = "pass" + "word" + ": hunter2"
        with tempfile.TemporaryDirectory() as td:
            repo = self._init_range_repo(Path(td))
            self._commit_file(repo, "before.txt", leak, message="unsafe path")
            subprocess.run([_git(), "-C", str(repo), "mv", "before.txt", "after.txt"], check=True)
            subprocess.run([_git(), "-C", str(repo), "commit", "-q", "-m", "rename"], check=True)
            rc, out, err = self._run_range(CANONICAL_SCANNER, repo, "origin", "claude")
            self.assertEqual(rc, 1, out + err)
            self.assertIn("PS-FINDING-CONTENT", err)

    def test_range_mode_root_history_without_published_seed_is_scanned(self) -> None:
        leak = "pass" + "word" + ": hunter2"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            origin = root / "origin.git"
            repo = root / "repo"
            subprocess.run([_git(), "init", "-q", "--bare", str(origin)], check=True)
            subprocess.run(
                [_git(), "init", "-q", "-b", "claude", str(repo)], check=True
            )
            subprocess.run([_git(), "-C", str(repo), "config", "user.email", "t@t"], check=True)
            subprocess.run([_git(), "-C", str(repo), "config", "user.name", "t"], check=True)
            subprocess.run([_git(), "-C", str(repo), "remote", "add", "origin", str(origin)], check=True)
            self._commit_file(repo, "root.txt", leak, message="root commit")
            rc, out, err = self._run_range(CANONICAL_SCANNER, repo, "origin", "claude")
            self.assertEqual(rc, 1, out + err)
            self.assertIn("PS-FINDING-CONTENT", err)

    def test_range_mode_merge_parent_history_is_scanned_after_tip_delete(self) -> None:
        leak = "pass" + "word" + ": hunter2"
        with tempfile.TemporaryDirectory() as td:
            repo = self._init_range_repo(Path(td))
            base = subprocess.run(
                [_git(), "-C", str(repo), "branch", "--show-current"],
                check=True, capture_output=True, text=True,
            ).stdout.strip()
            subprocess.run([_git(), "-C", str(repo), "checkout", "-q", "-b", "side"], check=True)
            self._commit_file(repo, "side-secret.txt", leak, message="side secret")
            subprocess.run([_git(), "-C", str(repo), "checkout", "-q", base], check=True)
            self._commit_file(repo, "main.txt", "clean main", message="main change")
            subprocess.run(
                [_git(), "-C", str(repo), "merge", "--no-ff", "-q", "side", "-m", "merge side"],
                check=True,
            )
            self._rm_file(repo, "side-secret.txt", message="delete merged secret")
            rc, out, err = self._run_range(CANONICAL_SCANNER, repo, "origin", "claude")
            self.assertEqual(rc, 1, out + err)
            self.assertIn("PS-FINDING-CONTENT", err)

    def test_range_mode_shared_blob_keeps_path_local_scanner_exemption(self) -> None:
        content = CANONICAL_SCANNER.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as td:
            repo = self._init_range_repo(Path(td))
            first = repo / "scripts" / "check-publication-safety.py"
            second = repo / "copies" / "not-the-scanner.py"
            first.parent.mkdir(parents=True)
            second.parent.mkdir(parents=True)
            first.write_text(content, encoding="utf-8")
            second.write_text(content, encoding="utf-8")
            subprocess.run([_git(), "-C", str(repo), "add", "scripts", "copies"], check=True)
            subprocess.run([_git(), "-C", str(repo), "commit", "-q", "-m", "shared blob"], check=True)
            rc, out, err = self._run_range(CANONICAL_SCANNER, repo, "origin", "claude")
            self.assertEqual(rc, 1, out + err)
            self.assertIn("PS-FINDING-CONTENT", err)

    def test_range_mode_deduplicates_blob_bytes_but_keeps_each_subject(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = self._init_range_repo(Path(td))
            for name in ("a.txt", "b.txt"):
                (repo / name).write_text("shared clean\n", encoding="utf-8")
            expected_blob_bytes = sum(
                len((repo / name).read_bytes()) for name in ("seed.txt", "a.txt")
            )
            subprocess.run([_git(), "-C", str(repo), "add", "a.txt", "b.txt"], check=True)
            subprocess.run([_git(), "-C", str(repo), "commit", "-q", "-m", "shared clean blob"], check=True)
            rc, out, err = self._run_range(CANONICAL_SCANNER, repo, "origin", "claude")
            self.assertEqual(rc, 0, err)
            self.assertIn("blobs=2", out)
            self.assertIn(f"blob-bytes={expected_blob_bytes}", out)
            self.assertIn("text=2, binary=0", out)
            self.assertIn("subjects=4", out)
            self.assertIn("paths=3", out)

    def test_range_mode_same_raw_path_with_two_blobs_binds_two_detector_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = self._init_range_repo(Path(td))
            self._commit_file(repo, "versioned.txt", "clean version one")
            self._commit_file(repo, "versioned.txt", "clean version two")
            rc, out, err = self._run_range(CANONICAL_SCANNER, repo, "origin", "claude")
            self.assertEqual(rc, 0, err)
            self.assertIn("blobs=3", out)
            self.assertIn("subjects=5", out)
            self.assertIn("paths=3", out)

    def test_range_mode_receipt_records_explicit_text_and_binary_disposition(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = self._init_range_repo(Path(td))
            text_fixture = repo / "text.txt"
            binary_fixture = repo / "binary.bin"
            text_fixture.write_text("clean text\n", encoding="utf-8")
            binary_fixture.write_bytes(b"\0\xff\x01")
            expected_blob_bytes = (
                len((repo / "seed.txt").read_bytes())
                + len(text_fixture.read_bytes())
                + len(binary_fixture.read_bytes())
            )
            subprocess.run([_git(), "-C", str(repo), "add", "text.txt", "binary.bin"], check=True)
            subprocess.run([_git(), "-C", str(repo), "commit", "-q", "-m", "mixed blobs"], check=True)
            rc, out, err = self._run_range(CANONICAL_SCANNER, repo, "origin", "claude")
            self.assertEqual(rc, 0, err)
            self.assertIn("blobs=3", out)
            self.assertIn(f"blob-bytes={expected_blob_bytes}", out)
            self.assertIn("text=2, binary=1", out)

    def test_range_mode_binary_blob_with_secret_marker_blocks_and_redacts(self) -> None:
        sentinel = "A1B2C3D4E5F6G7H8IJK"
        leak = _join("to", "ken", " = ", sentinel).encode("ascii")
        with tempfile.TemporaryDirectory() as td:
            repo = self._init_range_repo(Path(td))
            (repo / "binary-secret.bin").write_bytes(b"\0prefix " + leak + b" suffix")
            subprocess.run([_git(), "-C", str(repo), "add", "binary-secret.bin"], check=True)
            subprocess.run([_git(), "-C", str(repo), "commit", "-q", "-m", "binary payload"], check=True)
            rc, out, err = self._run_range(CANONICAL_SCANNER, repo, "origin", "claude")
            self.assertEqual(rc, 1, out + err)
            self.assertIn("PS-FINDING-CONTENT", err)
            self.assertNotIn(sentinel, out + err)

    def test_range_mode_decoy_scanner_basename_has_no_exemption(self) -> None:
        content = CANONICAL_SCANNER.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as td:
            repo = self._init_range_repo(Path(td))
            self._commit_file(
                repo,
                "decoy/check-publication-safety.py",
                content,
                message="decoy scanner basename",
            )
            rc, out, err = self._run_range(CANONICAL_SCANNER, repo, "origin", "claude")
            self.assertEqual(rc, 1, out + err)
            self.assertIn("PS-FINDING-CONTENT", err)

    def test_range_mode_exact_scanner_owner_paths_keep_catalog_exemption(self) -> None:
        content = CANONICAL_SCANNER.read_text(encoding="utf-8")
        approved = (
            "scripts/universal-hooks/scripts/check-publication-safety.py",
            "src.codex/skills/lead/scripts/check-publication-safety.py",
            "src.claude/agents/scripts/check-publication-safety.py",
        )
        for path in approved:
            with self.subTest(path=path), tempfile.TemporaryDirectory() as td:
                repo = self._init_range_repo(Path(td))
                self._commit_file(repo, path, content, message="approved scanner owner")
                rc, out, err = self._run_range(CANONICAL_SCANNER, repo, "origin", "claude")
                self.assertEqual(rc, 0, out + err)
                self.assertIn("receipt=v3", out)

    def test_bounded_oid_reader_refuses_count_bytes_and_deadline(self) -> None:
        module = _load_canonical_scanner("_scanner_v3_oid_stream")
        oid = "1" * 40

        async def run_row(body: str, *, count_cap: int, byte_cap: int, timeout: float):
            deadline = asyncio.get_running_loop().time() + timeout
            return await module._read_git_oid_lines_bounded(
                (sys.executable, "-u", "-c", body),
                count_cap=count_cap,
                byte_cap=byte_cap,
                deadline=deadline,
            )

        rows = {
            "count": (
                "import sys;sys.stdout.buffer.write(b'1'*40+b'\\n'+b'2'*40+b'\\n'+b'3'*40+b'\\n')",
                2,
                1_000,
                1.0,
                "PS-MSG-LIMIT",
            ),
            "bytes": (
                "import sys;sys.stdout.buffer.write(b'1'*40+b'\\n')",
                2,
                40,
                1.0,
                "PS-MSG-LIMIT",
            ),
            "deadline": (
                "import time;time.sleep(60)",
                2,
                1_000,
                0.1,
                "PS-MSG-READ-TIMEOUT",
            ),
            "duplicate": (
                "import sys;sys.stdout.buffer.write((b'1'*40+b'\\n')*2)",
                2,
                1_000,
                1.0,
                "PS-MSG-FRAME",
            ),
            "malformed": (
                "import sys;sys.stdout.buffer.write(b'x'*40+b'\\n')",
                2,
                1_000,
                1.0,
                "PS-MSG-FRAME",
            ),
        }
        for name, (body, count_cap, byte_cap, timeout, failure_id) in rows.items():
            with self.subTest(name=name):
                result = asyncio.run(run_row(
                    body, count_cap=count_cap, byte_cap=byte_cap, timeout=timeout
                ))
                self.assertIsInstance(result, module.Refusal)
                self.assertEqual(result.failure_id, failure_id, result)

    def test_tree_traversal_refuses_frontier_visit_and_cache_caps(self) -> None:
        deadline_module = _load_canonical_scanner("_scanner_v3_tree_deadline")

        async def expired_guard():
            loop = asyncio.get_running_loop()
            return deadline_module._tree_traversal_guard(
                deadline=loop.time() - 1.0,
                frontier=0,
                visits=0,
                visited=0,
                cache_entries=0,
            )

        deadline_refusal = asyncio.run(expired_guard())
        self.assertEqual(deadline_refusal.failure_id, "PS-MSG-READ-TIMEOUT")

        with tempfile.TemporaryDirectory() as td:
            repo = self._init_range_repo(Path(td))
            self._commit_file(repo, "nested/value.txt", "clean nested value")
            previous = Path.cwd()
            try:
                os.chdir(repo)
                for name in (
                    "_MAX_TREE_FRONTIER",
                    "_MAX_TREE_VISITS",
                    "_MAX_TREE_CACHE_ENTRIES",
                ):
                    module = _load_canonical_scanner("_scanner_v3_tree_" + name.lower())
                    setattr(module, name, 0)
                    with self.subTest(cap=name):
                        outcome = module._scan_range(
                            "origin", "claude", lambda _line: []
                        )
                        self.assertEqual(outcome.kind, "refusal")
                        self.assertEqual(outcome.refusal.failure_id, "PS-MSG-LIMIT")
            finally:
                os.chdir(previous)

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
                    self._commit_file(
                        repo,
                        "scripts/universal-hooks/scripts/check-publication-safety.py",
                        content,
                        message="add scanner",
                    )
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
        # Remote selection is an exact configured name; glob-like input must
        # never select or combine configured push destinations.
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
class TestPublicationSafetyScannerV3(unittest.TestCase):
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

    def _init_range_repo(
        self,
        root: Path,
        *,
        publish_seed: bool = True,
        object_format: str = "sha1",
    ) -> Path:
        origin = root / "origin.git"
        repo = root / "repo"
        format_args = [] if object_format == "sha1" else [f"--object-format={object_format}"]
        subprocess.run(
            [_git(), "init", "-q", "--bare", *format_args, str(origin)], check=True
        )
        subprocess.run(
            [_git(), "init", "-q", "-b", "main", *format_args, str(repo)], check=True
        )
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

    @unittest.skipUnless(
        sys.platform.startswith("linux"), "Linux shared subreaper owner"
    )
    def test_default_range_path_finishes_reader_before_tip_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = self._init_range_repo(Path(td))
            self._commit(repo, "candidate.txt", "clean candidate", "candidate")
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(CANONICAL_SCANNER),
                    "--range",
                    "origin",
                    "main",
                ],
                cwd=repo,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                start_new_session=True,
            )
            try:
                stdout, stderr = process.communicate(timeout=8.0)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate(timeout=2.0)
                self.fail("default range path nested the process-wide owner")

            self.assertEqual(0, process.returncode, stdout + stderr)
            self.assertIn("receipt=v3", stdout)
            self.assertEqual("", stderr)

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
        frame = lambda value: len(value).to_bytes(8, "big") + value
        digest = hashlib.sha256(
            frame(b"publication-safety-range-receipt-v3")
            + frame(b"commit-set")
        )
        for value in ordered:
            digest.update(frame(value.encode("ascii")))
        return digest.hexdigest()

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

    def test_range_object_format_matrix_scans_complete_text_and_binary_graph(self) -> None:
        for object_format, oid_length in (("sha1", 40), ("sha256", 64)):
            with self.subTest(object_format=object_format), tempfile.TemporaryDirectory() as td:
                repo = self._init_range_repo(Path(td), object_format=object_format)
                self.assertEqual(
                    self._git_run(repo, "rev-parse", "--show-object-format").stdout.strip(),
                    object_format,
                )
                self._commit(repo, "nested/text.txt", "clean text", "clean text commit")
                (repo / "binary.bin").write_bytes(b"\0\1\2")
                self._git_run(repo, "add", "binary.bin")
                self._git_run(repo, "commit", "-q", "-m", "clean binary commit")
                tip = self._git_run(repo, "rev-parse", "HEAD").stdout.strip()
                commits = self._git_run(
                    repo, "rev-list", "--topo-order", "HEAD", "--not", "--remotes=origin"
                ).stdout.splitlines()
                objects = self._git_run(
                    repo,
                    "rev-list",
                    "--objects",
                    "--no-object-names",
                    "HEAD",
                    "--not",
                    "--remotes=origin",
                ).stdout.splitlines()

                proc = self._run_range(repo)

                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(len(tip), oid_length)
                self.assertTrue(all(len(oid) == oid_length for oid in commits))
                self.assertTrue(all(len(oid) == oid_length for oid in objects))
                self.assertIn(f"commits={len(commits)}", proc.stdout)
                self.assertIn(f"objects={len(objects)}", proc.stdout)
                self.assertIn("blobs=2", proc.stdout)
                self.assertIn("text=1", proc.stdout)
                self.assertIn("binary=1", proc.stdout)
                self.assertIn(f"tip={tip})", proc.stdout)

    def test_range_selection_refuses_unknown_git_object_format(self) -> None:
        module = _load_canonical_scanner("_scanner_v3_unknown_object_format")
        responses = (
            subprocess.CompletedProcess(["git", "remote"], 0, "origin\n", ""),
            subprocess.CompletedProcess(
                ["git", "rev-parse", "--show-object-format"], 0, "sha512\n", ""
            ),
        )
        with mock.patch.object(module, "_run_git", side_effect=responses):
            result = asyncio.run(module._range_selection(
                module.RangeRequest("origin", "main", "main")
            ))

        self.assertIsInstance(result, module.Refusal)
        self.assertEqual(result.failure_id, "PS-MSG-RANGE")
        self.assertEqual(result.phase, "selection")
        self.assertEqual(result.reason, "object-format")

    def test_v3_commit_set_digest_row_mutation(self) -> None:
        rows = ["1" * 40, "2" * 40, "3" * 40]
        for mutation in (rows[:-1], rows + [rows[-1]], [rows[0], rows[1], "4" * 40]):
            with self.subTest(mutation=tuple(mutation)):
                self.assertNotEqual(
                    self._expected_digest(rows), self._expected_digest(mutation)
                )

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
            self.assertIn("receipt=v3, commits=1", proc.stdout)
            self.assertIn("blobs=0", proc.stdout)
            self.assertIn("subjects=0", proc.stdout)
            self.assertIn("paths=0", proc.stdout)
            self.assertIn("messages=complete", proc.stdout)

    def test_range_fail_closed_matrix(self) -> None:
        module = _load_canonical_scanner("_scanner_v3_failures")
        for name in ("Refusal", "_decode_commit_message", "_parse_batch_header"):
            self.assertTrue(hasattr(module, name), name)
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
        module = _load_canonical_scanner("_scanner_v3_tip")
        self.assertTrue(hasattr(module, "_confirm_tip"))
        refusal = module._confirm_tip(
            "1" * 40, lambda _timeout=None: "2" * 40
        )
        self.assertEqual(refusal.failure_id, "PS-MSG-TIP-CHANGED")

    def test_range_destination_selects_named_commit_and_truthful_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = self._init_range_repo(Path(td))
            original_branch = self._git_run(
                repo, "branch", "--show-current"
            ).stdout.strip()
            self._git_run(repo, "switch", "-q", "-c", "candidate")
            candidate_tip = self._commit(
                repo, "candidate-only.txt", "clean candidate", "candidate"
            )
            self._git_run(repo, "switch", "-q", original_branch)
            self._commit(
                repo,
                "head-only.txt",
                _join("to", "ken", " = ", "A1B2C3D4E5F6G7H8IJK"),
                "unrelated head",
            )

            symbolic = self._run_range(repo, dst="candidate")
            full_sha = self._run_range(repo, dst=candidate_tip)

            self.assertEqual(symbolic.returncode, 0, symbolic.stderr)
            self.assertEqual(full_sha.returncode, 0, full_sha.stderr)
            self.assertIn("commits=2", symbolic.stdout)
            self.assertIn("paths=2", symbolic.stdout)
            self.assertIn(
                f"dst=candidate, src=candidate, tip={candidate_tip})",
                symbolic.stdout,
            )
            for field in (
                "commit-set", "object-set", "blob-set", "blob-bytes",
                "subject-set", "path-set", "tip",
            ):
                symbolic_value = symbolic.stdout.split(f"{field}=", 1)[1].split(",", 1)[0].rstrip(")\n")
                full_sha_value = full_sha.stdout.split(f"{field}=", 1)[1].split(",", 1)[0].rstrip(")\n")
                self.assertEqual(symbolic_value, full_sha_value, field)

    def test_range_destination_content_cannot_be_laundered_by_clean_head(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = self._init_range_repo(Path(td))
            original_branch = self._git_run(
                repo, "branch", "--show-current"
            ).stdout.strip()
            self._git_run(repo, "switch", "-q", "-c", "candidate")
            self._commit(
                repo,
                "candidate-only.txt",
                _join("to", "ken", " = ", "A1B2C3D4E5F6G7H8IJK"),
                "candidate",
            )
            self._git_run(repo, "switch", "-q", original_branch)
            self._commit(repo, "head-only.txt", "clean head", "unrelated head")

            proc = self._run_range(repo, dst="candidate")

            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("PS-FINDING-CONTENT", proc.stderr)
            self.assertNotIn("publication-safety: clean", proc.stdout + proc.stderr)

    def test_range_replace_ref_cannot_substitute_clean_commit_for_pushed_history(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = self._init_range_repo(Path(td))
            seed = self._git_run(repo, "rev-parse", "HEAD").stdout.strip()
            bad = self._commit(
                repo,
                "bad.txt",
                "clean body",
                self._leak_message("replace-original"),
            )
            tree = self._git_run(repo, "rev-parse", f"{bad}^{{tree}}").stdout.strip()
            replacement = self._git_run(
                repo,
                "commit-tree",
                tree,
                "-p",
                seed,
                input_text="clean replacement\n",
            ).stdout.strip()
            self._git_run(repo, "replace", bad, replacement)
            self._commit(repo, "tip.txt", "clean tip", "clean tip")

            proc = self._run_range(repo)

            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("PS-FINDING-COMMIT-MESSAGE", proc.stderr)
            self.assertNotIn("publication-safety: clean", proc.stdout + proc.stderr)

    def test_range_refuses_nonempty_graft_overlay_before_history_scan(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = self._init_range_repo(Path(td))
            seed = self._git_run(repo, "rev-parse", "HEAD").stdout.strip()
            self._commit(
                repo,
                "bad.txt",
                "clean body",
                self._leak_message("grafted-parent"),
            )
            tip = self._commit(repo, "tip.txt", "clean tip", "clean tip")
            grafts = repo / ".git" / "info" / "grafts"
            grafts.parent.mkdir(parents=True, exist_ok=True)
            grafts.write_text(f"{tip} {seed}\n", encoding="ascii")

            proc = self._run_range(repo)

            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            self.assertIn("PS-MSG-RANGE", proc.stderr)
            self.assertIn("reason=graft-overlay", proc.stderr)
            self.assertNotIn("publication-safety: clean", proc.stdout + proc.stderr)

    def test_range_excludes_only_authoritative_destination_oid(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = self._init_range_repo(Path(td))
            bad = self._commit(
                repo,
                "bad.txt",
                "clean body",
                self._leak_message("stale-local-remote"),
            )
            self._git_run(repo, "update-ref", "refs/remotes/origin/decoy", bad)
            self._commit(repo, "tip.txt", "clean tip", "clean tip")

            proc = self._run_range(repo)

            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("PS-FINDING-COMMIT-MESSAGE", proc.stderr)
            self.assertNotIn("publication-safety: clean", proc.stdout + proc.stderr)

    def test_range_timeout_reaps_spawned_git_process_tree(self) -> None:
        module = _load_canonical_scanner("_scanner_v3_range_tree_timeout")
        self.assertTrue(hasattr(module, "_run_owned_process"))
        with tempfile.TemporaryDirectory() as td:
            child_pid_path = Path(td) / "child.pid"
            wrapper = (
                "import pathlib,subprocess,sys,time;"
                "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);"
                "pathlib.Path(sys.argv[1]).write_text(str(child.pid),encoding='ascii');"
                "time.sleep(60)"
            )
            with self.assertRaises(subprocess.TimeoutExpired):
                module._run_owned_process(
                    [sys.executable, "-c", wrapper, str(child_pid_path)],
                    timeout=0.5,
                )
            self.assertTrue(child_pid_path.exists(), "wrapper did not spawn its sleeper")
            child_pid = int(child_pid_path.read_text(encoding="ascii"))
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                try:
                    os.kill(child_pid, 0)
                except OSError:
                    break
                time.sleep(0.05)
            else:
                self.fail("timed-out range Git process left its sleeper child alive")

    @unittest.skipIf(os.name == "nt", "POSIX process-group regression")
    def test_posix_timeout_preserves_result_after_group_reap(self) -> None:
        module = _load_canonical_scanner("_scanner_v3_posix_timeout_order")
        with tempfile.TemporaryDirectory() as td:
            pids_path = Path(td) / "pids"
            wrapper = (
                "import os,pathlib,subprocess,sys,time;"
                "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],"
                "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);"
                "pathlib.Path(sys.argv[1]).write_text(f'{os.getpid()} {child.pid}',encoding='ascii');"
                "time.sleep(60)"
            )
            with self.assertRaises(subprocess.TimeoutExpired):
                module._run_owned_process(
                    [sys.executable, "-c", wrapper, str(pids_path)], timeout=0.5
                )
            group_pid = int(pids_path.read_text(encoding="ascii").split()[0])
            with self.assertRaises(ProcessLookupError):
                os.killpg(group_pid, 0)

    @unittest.skipIf(os.name == "nt", "POSIX bounded sync cleanup")
    def test_posix_timeout_preserves_output_with_bounded_post_settlement_communicate(
        self,
    ) -> None:
        module = _load_canonical_scanner("_scanner_sync_bounded_communicate")
        real_popen = module.subprocess.Popen
        communicate_timeouts: list[float | None] = []

        class RecordingProcess:
            def __init__(self, *args, **kwargs):
                self._process = real_popen(*args, **kwargs)

            def __getattr__(self, name):
                return getattr(self._process, name)

            def communicate(self, *args, **kwargs):
                communicate_timeouts.append(kwargs.get("timeout"))
                return self._process.communicate(*args, **kwargs)

        module.subprocess.Popen = RecordingProcess
        started = time.monotonic()
        try:
            with self.assertRaises(subprocess.TimeoutExpired) as captured:
                module._run_owned_process(
                    [
                        sys.executable,
                        "-u",
                        "-c",
                        "import time;print('before-timeout',flush=True);time.sleep(60)",
                    ],
                    timeout=0.2,
                    text=True,
                )
        finally:
            module.subprocess.Popen = real_popen

        self.assertLess(time.monotonic() - started, 4.0)
        self.assertGreaterEqual(len(communicate_timeouts), 2)
        self.assertEqual(0.2, communicate_timeouts[0])
        self.assertIsNotNone(communicate_timeouts[1])
        self.assertIn("before-timeout", captured.exception.output)

    @unittest.skipUnless(
        sys.platform.startswith("linux"), "Linux sync BaseException cleanup"
    )
    def test_posix_keyboard_interrupt_settles_and_reraises_original(self) -> None:
        module = _load_canonical_scanner("_scanner_sync_keyboard_interrupt")
        helper = module._POSIX_PROCESS_GROUP
        initial_state = _linux_child_subreaper_state()
        real_popen = module.subprocess.Popen
        interruption = KeyboardInterrupt("injected-communicate-interrupt")
        created = []

        class InterruptingProcess:
            def __init__(self, *args, **kwargs):
                self._process = real_popen(*args, **kwargs)
                self._first = True
                created.append(self)

            def __getattr__(self, name):
                return getattr(self._process, name)

            def communicate(self, *args, **kwargs):
                if self._first:
                    self._first = False
                    raise interruption
                return self._process.communicate(*args, **kwargs)

        module.subprocess.Popen = InterruptingProcess
        observed_locked = True
        observed_group = True
        observed_closed = False
        try:
            with self.assertRaises(KeyboardInterrupt) as captured:
                module._run_owned_process(
                    [sys.executable, "-c", "import time;time.sleep(60)"],
                    timeout=2.0,
                )
            self.assertIs(interruption, captured.exception)
            observed_locked = helper._LINUX_SUBREAPER_LOCK.locked()
            process = created[0]
            try:
                os.killpg(process.pid, 0)
            except ProcessLookupError:
                observed_group = False
            observed_closed = process.stdout.closed and process.stderr.closed
        finally:
            module.subprocess.Popen = real_popen
            if created:
                process = created[0]
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                try:
                    process._process.communicate(timeout=2.0)
                except (subprocess.TimeoutExpired, OSError, ValueError):
                    pass
            _set_linux_child_subreaper_state(initial_state)
            if helper._LINUX_SUBREAPER_LOCK.locked():
                helper._LINUX_SUBREAPER_LOCK.release()

        self.assertFalse(observed_locked)
        self.assertFalse(observed_group)
        self.assertTrue(observed_closed)

    @unittest.skipUnless(
        sys.platform.startswith("linux"), "Linux child-subreaper regression"
    )
    def test_posix_success_reaps_ignoring_descendant_after_parent_exits(self) -> None:
        module = _load_canonical_scanner("_scanner_v3_posix_exited_parent")
        with tempfile.TemporaryDirectory() as td:
            pids_path = Path(td) / "pids"
            ready_path = Path(td) / "ready"
            wrapper = (
                "import os,pathlib,subprocess,sys,time;"
                "code=\"import os,pathlib,signal,sys,time\\n"
                "signal.signal(signal.SIGTERM,signal.SIG_IGN)\\n"
                "[os.close(fd) for fd in (0,1,2)]\\n"
                "pathlib.Path(sys.argv[1]).write_text('ready',encoding='ascii')\\n"
                "time.sleep(60)\";"
                "child=subprocess.Popen([sys.executable,'-c',code,sys.argv[2]]);"
                "deadline=time.monotonic()+5;"
                "exec(\"while not pathlib.Path(sys.argv[2]).is_file():\\n"
                "    assert time.monotonic()<deadline\\n"
                "    time.sleep(0.01)\");"
                "pathlib.Path(sys.argv[1]).write_text("
                "f'{os.getpid()} {child.pid}',encoding='ascii')"
            )

            result = module._run_owned_process(
                [
                    sys.executable,
                    "-c",
                    wrapper,
                    str(pids_path),
                    str(ready_path),
                ],
                timeout=2.0,
            )

            self.assertEqual(0, result.returncode)
            process_group, descendant_pid = map(
                int, pids_path.read_text(encoding="ascii").split()
            )
            with self.assertRaises(ProcessLookupError):
                os.killpg(process_group, 0)
            self.assertFalse(Path(f"/proc/{descendant_pid}").exists())

    @unittest.skipIf(os.name == "nt", "POSIX process-group regression")
    def test_posix_async_cancel_returns_refusal_after_group_reap(self) -> None:
        module = _load_canonical_scanner("_scanner_v3_posix_cancel_order")
        with tempfile.TemporaryDirectory() as td:
            pids_path = Path(td) / "pids"
            wrapper = (
                "import os,pathlib,subprocess,sys,time;"
                "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],"
                "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);"
                "pathlib.Path(sys.argv[1]).write_text(f'{os.getpid()} {child.pid}',encoding='ascii');"
                "time.sleep(60)"
            )

            async def exercise_cancel():
                task = asyncio.create_task(module._read_git_lines_bounded(
                    (sys.executable, "-u", "-c", wrapper, str(pids_path)),
                    byte_cap=1024,
                    line_cap=256,
                    deadline=asyncio.get_running_loop().time() + 5.0,
                    accepted_codes=frozenset({0}),
                ))
                deadline = asyncio.get_running_loop().time() + 1.0
                while not pids_path.exists():
                    self.assertLess(asyncio.get_running_loop().time(), deadline)
                    await asyncio.sleep(0.01)
                task.cancel()
                return await task

            outcome = asyncio.run(exercise_cancel())
            self.assertIsInstance(outcome, module.Refusal)
            self.assertEqual(outcome.reason, "cancelled")
            group_pid = int(pids_path.read_text(encoding="ascii").split()[0])
            with self.assertRaises(ProcessLookupError):
                os.killpg(group_pid, 0)

    @unittest.skipUnless(
        sys.platform.startswith("linux"), "Linux asyncio child observation"
    )
    def test_async_owner_observes_direct_status_without_stealing_child_reap(self) -> None:
        module = _load_canonical_scanner("_scanner_async_direct_observation")

        async def exercise():
            process, owner, observation = await module._create_owned_async_process(
                (sys.executable, "-c", "raise SystemExit(7)"),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(asyncio.shield(observation.task), timeout=2.0)
            settled = await module._settle_owned_async_process(
                process,
                owner,
                observation,
                drain_readers=(process.stdout, process.stderr),
            )
            return process, observation, settled

        process, observation, settled = asyncio.run(exercise())
        self.assertTrue(settled)
        self.assertEqual(7, process.returncode)
        self.assertEqual(7, observation.poll())
        self.assertTrue(observation.task.done())

    @unittest.skipUnless(
        sys.platform.startswith("linux"), "Linux asyncio group signal ownership"
    )
    def test_async_owner_alone_sends_term_then_kill(self) -> None:
        module = _load_canonical_scanner("_scanner_async_owner_signals")
        helper = module._POSIX_PROCESS_GROUP
        real_os = helper.os
        signals: list[int] = []
        temp = tempfile.TemporaryDirectory()
        ready = Path(temp.name) / "ready"

        def killpg(process_group: int, signum: int) -> None:
            if signum:
                signals.append(signum)
            real_os.killpg(process_group, signum)

        helper.os = SimpleNamespace(
            **{
                name: getattr(real_os, name)
                for name in dir(real_os)
                if not name.startswith("__") and name != "killpg"
            },
            killpg=killpg,
        )
        try:
            async def exercise():
                process, owner, observation = await module._create_owned_async_process(
                    (
                        sys.executable,
                        "-c",
                        "import pathlib,signal,sys,time;"
                        "signal.signal(signal.SIGTERM,signal.SIG_IGN);"
                        "pathlib.Path(sys.argv[1]).write_text('ready',encoding='ascii');"
                        "time.sleep(60)",
                        str(ready),
                    ),
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                process.terminate = mock.Mock(
                    side_effect=AssertionError("async transport terminate called")
                )
                process.kill = mock.Mock(
                    side_effect=AssertionError("async transport kill called")
                )
                deadline = asyncio.get_running_loop().time() + 2.0
                while not ready.is_file():
                    self.assertLess(asyncio.get_running_loop().time(), deadline)
                    await asyncio.sleep(0.01)
                settled = await module._settle_owned_async_process(
                    process,
                    owner,
                    observation,
                    timeout_seconds=1.0,
                    drain_readers=(process.stdout, process.stderr),
                )
                return process, observation, settled

            process, observation, settled = asyncio.run(exercise())
        finally:
            helper.os = real_os
            temp.cleanup()

        self.assertTrue(settled)
        self.assertEqual([signal.SIGTERM, signal.SIGKILL], signals)
        self.assertIsNotNone(process.returncode)
        self.assertEqual(process.returncode, observation.poll())

    @unittest.skipUnless(
        sys.platform.startswith("linux"), "Linux asyncio output drain"
    )
    def test_async_one_shot_settlement_drains_output_to_eof_without_pending_task(self) -> None:
        module = _load_canonical_scanner("_scanner_async_output_drain")

        async def exercise():
            process, owner, observation = await module._create_owned_async_process(
                (
                    sys.executable,
                    "-c",
                    "import os,time;os.write(1,b'x'*65536);time.sleep(60)",
                ),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            settled = await module._settle_owned_async_process(
                process,
                owner,
                observation,
                timeout_seconds=1.0,
                drain_readers=(process.stdout, process.stderr),
            )
            pending = {
                task
                for task in asyncio.all_tasks()
                if task is not asyncio.current_task() and not task.done()
            }
            return process, observation, settled, pending

        process, observation, settled, pending = asyncio.run(exercise())
        self.assertTrue(settled)
        self.assertTrue(process.stdout.at_eof())
        self.assertTrue(process.stderr.at_eof())
        self.assertTrue(observation.task.done())
        self.assertEqual(set(), pending)

    def test_range_settles_descendants_after_parent_exit(self) -> None:
        module = _load_canonical_scanner("_scanner_v3_range_parent_exit")
        for exit_code in (0, 7):
            with self.subTest(exit_code=exit_code), tempfile.TemporaryDirectory() as td:
                child_pid_path = Path(td) / "child.pid"
                wrapper = (
                    "import pathlib,subprocess,sys;"
                    "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],"
                    "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);"
                    "pathlib.Path(sys.argv[1]).write_text(str(child.pid),encoding='ascii');"
                    "sys.exit(int(sys.argv[2]))"
                )
                outcome = module._run_owned_process(
                    [
                        sys.executable, "-c", wrapper, str(child_pid_path),
                        str(exit_code),
                    ],
                    timeout=2.0,
                )
                self.assertEqual(outcome.returncode, exit_code)
                child_pid = int(child_pid_path.read_text(encoding="ascii"))
                try:
                    os.kill(child_pid, 0)
                except OSError:
                    pass
                else:
                    self.fail(
                        f"range parent exit {exit_code} left its sleeper child alive"
                    )

    def test_object_reader_close_settles_exited_parent_descendants(self) -> None:
        module = _load_canonical_scanner("_scanner_v3_reader_close_tree")
        with tempfile.TemporaryDirectory() as td:
            child_pid_path = Path(td) / "child.pid"
            wrapper = (
                "import pathlib,subprocess,sys;"
                "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],"
                "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);"
                "pathlib.Path(sys.argv[1]).write_text(str(child.pid),encoding='ascii');"
                "sys.stdin.buffer.read()"
            )

            async def exercise_reader_close():
                reader = module.ObjectReaderSession(
                    argv=(sys.executable, "-u", "-c", wrapper, str(child_pid_path)),
                    request_timeout=1.0,
                    settle_timeout=1.0,
                )
                self.assertIsNone(await reader.start())
                deadline = asyncio.get_running_loop().time() + 1.0
                while not child_pid_path.exists():
                    self.assertLess(asyncio.get_running_loop().time(), deadline)
                    await asyncio.sleep(0.01)
                self.assertIsNone(await reader.finalize())

            asyncio.run(exercise_reader_close())
            child_pid = int(child_pid_path.read_text(encoding="ascii"))
            try:
                os.kill(child_pid, 0)
            except OSError:
                pass
            else:
                self.fail("object-reader close left its sleeper child alive")

    def test_range_remote_probe_keeps_pushurl_out_of_child_argv_and_diagnostics(self) -> None:
        module = _load_canonical_scanner("_scanner_v3_pushurl_transport")
        canary = _join("https://probe-user:", "credential-canary", "@example.invalid/repo.git")
        captured: dict[str, object] = {}

        async def fake_reader(argv, **kwargs):
            captured["argv"] = argv
            captured["env"] = kwargs.get("env")
            return 2, ()

        stderr = io.StringIO()
        async def exercise_remote_probe():
            return await module._remote_destination_oid(
                canary,
                "main",
                deadline=asyncio.get_running_loop().time() + 5.0,
                object_format=module._SHA1_OBJECT_FORMAT,
            )

        with mock.patch.object(module, "_read_git_lines_bounded", side_effect=fake_reader):
            with contextlib.redirect_stderr(stderr):
                outcome = asyncio.run(exercise_remote_probe())

        self.assertIsNone(outcome)
        argv_diagnostics = repr(captured.get("argv")) + stderr.getvalue()
        self.assertNotIn(canary, argv_diagnostics)
        child_env = captured.get("env")
        self.assertIsInstance(child_env, dict)
        self.assertIn(canary, child_env.values())

    def test_range_uses_unique_pushurl_not_fetch_url_for_destination_oid(self) -> None:
        for push_has_seed in (True, False):
            with self.subTest(push_has_seed=push_has_seed), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                repo = self._init_range_repo(root)
                push_target = root / "push.git"
                subprocess.run(
                    [_git(), "init", "-q", "--bare", str(push_target)], check=True
                )
                seed = self._git_run(repo, "rev-parse", "HEAD").stdout.strip()
                if push_has_seed:
                    self._git_run(
                        repo,
                        "push",
                        "-q",
                        str(push_target),
                        f"{seed}:refs/heads/main",
                    )
                self._commit(
                    repo,
                    "bad.txt",
                    "clean body",
                    self._leak_message("fetch-ahead-push-behind"),
                )
                self._git_run(repo, "push", "-q", "origin", "HEAD:refs/heads/main")
                self._commit(repo, "tip.txt", "clean tip", "clean tip")
                self._git_run(
                    repo, "config", "remote.origin.pushurl", str(push_target)
                )

                proc = self._run_range(repo)

                self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
                self.assertIn("PS-FINDING-COMMIT-MESSAGE", proc.stderr)
                self.assertNotIn("publication-safety: clean", proc.stdout + proc.stderr)

    def test_range_refuses_multiple_configured_push_destinations(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = self._init_range_repo(root)
            first = root / "push-one.git"
            second = root / "push-two.git"
            for target in (first, second):
                subprocess.run([_git(), "init", "-q", "--bare", str(target)], check=True)
                self._git_run(
                    repo, "config", "--add", "remote.origin.pushurl", str(target)
                )
            self._commit(repo, "tip.txt", "clean tip", "clean tip")

            proc = self._run_range(repo)

            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            self.assertIn("PS-MSG-RANGE", proc.stderr)
            self.assertIn("reason=push-destination", proc.stderr)
            self.assertNotIn("publication-safety: clean", proc.stdout + proc.stderr)

    def test_range_source_override_is_explicit_and_truthful_in_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = self._init_range_repo(Path(td))
            original_branch = self._git_run(
                repo, "branch", "--show-current"
            ).stdout.strip()
            self._git_run(repo, "switch", "-q", "-c", "candidate")
            self._commit(repo, "candidate.txt", "clean candidate", "candidate")
            self._git_run(repo, "switch", "-q", original_branch)
            source_tip = self._commit(repo, "source.txt", "clean source", "source")

            proc = subprocess.run(
                [
                    sys.executable, str(CANONICAL_SCANNER),
                    "--range", "origin", "candidate",
                    "--range-source", source_tip,
                ],
                cwd=repo,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn(
                f"dst=candidate, src={source_tip}, tip={source_tip})",
                proc.stdout,
            )

    def test_range_destination_refuses_missing_and_noncommit_objects(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = self._init_range_repo(Path(td))
            blob = self._git_run(repo, "rev-parse", "HEAD:seed.txt").stdout.strip()
            self._git_run(repo, "update-ref", "refs/tags/blob-only", blob)

            for destination in ("missing", "refs/tags/blob-only"):
                with self.subTest(destination=destination):
                    proc = self._run_range(repo, dst=destination)
                    self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
                    self.assertIn("id=PS-MSG-RANGE", proc.stderr)
                    self.assertNotIn("publication-safety: clean", proc.stdout + proc.stderr)

    def test_range_destination_drift_refuses_after_real_acquisition(self) -> None:
        module = _load_canonical_scanner("_scanner_v3_destination_drift")
        with tempfile.TemporaryDirectory() as td:
            repo = self._init_range_repo(Path(td))
            original_branch = self._git_run(
                repo, "branch", "--show-current"
            ).stdout.strip()
            self._git_run(repo, "switch", "-q", "-c", "candidate")
            self._commit(repo, "candidate-only.txt", "clean candidate", "candidate")
            self._git_run(repo, "switch", "-q", original_branch)
            replacement_tip = self._commit(
                repo, "replacement.txt", "clean replacement", "replacement"
            )
            moved = False

            def move_destination(_event, _oid) -> None:
                nonlocal moved
                if not moved:
                    self._git_run(
                        repo, "update-ref", "refs/heads/candidate", replacement_tip
                    )
                    moved = True

            with contextlib.chdir(repo):
                outcome = asyncio.run(module._scan_range_async(
                    "origin", "candidate", lambda _line: [],
                    coverage_observer=move_destination,
                ))

            self.assertTrue(moved)
            self.assertEqual(outcome.kind, "refusal")
            self.assertEqual(outcome.refusal.failure_id, "PS-MSG-TIP-CHANGED")

    def test_range_destination_ignores_unrelated_head_drift(self) -> None:
        module = _load_canonical_scanner("_scanner_v3_unrelated_head")
        with tempfile.TemporaryDirectory() as td:
            repo = self._init_range_repo(Path(td))
            original_branch = self._git_run(
                repo, "branch", "--show-current"
            ).stdout.strip()
            self._git_run(repo, "switch", "-q", "-c", "candidate")
            candidate_tip = self._commit(
                repo, "candidate-only.txt", "clean candidate", "candidate"
            )
            self._git_run(repo, "switch", "-q", original_branch)
            self._commit(repo, "head-only.txt", "clean head", "unrelated head")
            moved = False

            def move_head(_event, _oid) -> None:
                nonlocal moved
                if not moved:
                    self._git_run(
                        repo, "symbolic-ref", "HEAD", "refs/heads/candidate"
                    )
                    moved = True

            with contextlib.chdir(repo):
                outcome = asyncio.run(module._scan_range_async(
                    "origin", "candidate", lambda _line: [],
                    coverage_observer=move_head,
                ))

            self.assertTrue(moved)
            self.assertEqual(outcome.kind, "clean", outcome.refusal)
            self.assertEqual(outcome.selection.tip, candidate_tip)

    def test_receipt_v3_canonicalization(self) -> None:
        module = _load_canonical_scanner("_scanner_v3_receipt")
        rows = ["2" * 40, "1" * 40]
        selection = module.RangeSelection(
            "origin one", "refs/heads/topic", "refs/heads/topic", "2" * 40,
            tuple(rows), tuple(rows),
        )
        history = _empty_history_proof(module, selection)
        line = module._serialize_range_receipt_v3(
            history, selection.remote, selection.destination,
            selection.source, selection.tip,
        )
        self.assertEqual(
            line,
            "publication-safety: clean (range, receipt=v3, commits=2, "
            f"commit-set={self._expected_digest(rows)}, messages=complete, "
            f"objects=2, object-set={history.object_set}, blobs=0, "
            f"blob-set={history.blob_set}, blob-bytes=0, text=0, binary=0, "
            f"subjects=0, subject-set={history.subject_set}, paths=0, "
            f"path-set={history.path_set}, history=complete, "
            "remote=origin%20one, dst=refs%2Fheads%2Ftopic, "
            "src=refs%2Fheads%2Ftopic, tip=" + "2" * 40 + ")",
        )
        self.assertFalse(hasattr(module, "_serialize_range_receipt_v2"))

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
        selection = module.RangeSelection(
            "origin", "refs/heads/main", "refs/heads/main", oid,
            (oid,), (oid,)
        )
        originals = (module._range_selection, module._acquire_history)

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

            async def finalize(self):
                self.finalize_calls += 1
                if self.row == "cleanup-refusal":
                    self.state = module.ReaderState.REAP_PENDING
                    return module._refusal("PS-MSG-REAP", "unreaped")
                self.reap_certificate = complete_certificate()
                self.state = module.ReaderState.REAPED
                return None

        async def exercise() -> None:
            module._range_selection = mock.AsyncMock(return_value=selection)

            async def acquire(
                selected, reader, find_machine_paths, recorder, _deadline
            ):
                if reader.row == "read-exception":
                    raise RuntimeError("synthetic")
                if reader.row == "read-refusal":
                    return module._refusal("PS-MSG-READ", "short-read")
                if reader.row == "decode-refusal":
                    return module._refusal("PS-MSG-FRAME", "commit-separator")
                recorder.record(module.CoverageEvent.REQUESTED, oid)
                recorder.record(
                    module.CoverageEvent.ACQUIRED,
                    other if reader.row == "coverage-refusal" else oid,
                )
                findings = module._content_hits(
                    "clean", oid, find_machine_paths,
                    subject_kind="commit-message",
                )
                recorder.record(module.CoverageEvent.SCANNED, oid)
                coverage = recorder.proof()
                if isinstance(coverage, module.Refusal):
                    return coverage
                return (
                    _empty_history_proof(module, selected),
                    coverage,
                    tuple(findings),
                )

            module._acquire_history = acquire
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
                    resolver = (
                        (lambda _timeout=None: other)
                        if row == "tip-drift"
                        else (lambda _timeout=None: oid)
                    )
                    outcome = await module._scan_range_async(
                        "origin", "refs/heads/main", lambda _line: [],
                        tip_resolver=resolver,
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
                        tip_resolver=lambda _timeout=None: oid,
                        reader_factory=lambda: reader,
                    )
                    self.assertEqual(outcome.kind, expected_kind)
                    self.assertTrue(outcome.reap_certificate.complete)
                    self.assertEqual(reader.finalize_calls, 1)

            reader = FakeReader("cleanup-refusal")
            outcome = await module._scan_range_async(
                "origin", "refs/heads/main", lambda _line: [],
                tip_resolver=lambda _timeout=None: oid,
                reader_factory=lambda: reader,
            )
            self.assertEqual(outcome.kind, "refusal")
            self.assertEqual(outcome.refusal.failure_id, "PS-MSG-REAP")
            self.assertIsNone(outcome.reap_certificate)
            self.assertEqual(reader.finalize_calls, 2)

        try:
            asyncio.run(exercise())
        finally:
            module._range_selection, module._acquire_history = originals


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
            finalize_reached = asyncio.Event()
            release_finalize = asyncio.Event()
            drive_finalizer = reader._drive_finalizer

            async def drive_finalizer_at_barrier():
                finalize_reached.set()
                await release_finalize.wait()
                return await drive_finalizer()

            reader._drive_finalizer = drive_finalizer_at_barrier
            try:
                task = asyncio.create_task(module._finalize_reader(reader))
                await asyncio.wait_for(finalize_reached.wait(), timeout=1.0)
                task.cancel()
                release_finalize.set()
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
                release_finalize.set()
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
            "origin", "refs/heads/main", "refs/heads/main", "2" * 40,
            (oid,), (oid,)
        )

        class Reader:
            def __init__(self, returned_oid=oid):
                self.returned_oid = returned_oid
                self.reap_certificate = None
                self.state = module.ReaderState.ACTIVE

            async def start(self):
                return None

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
            module._acquire_history,
            module._confirm_tip,
            module._content_hits,
        )

        async def acquire(selected, reader, finder, recorder, _deadline):
            oid_value = selected.expected_oids[0]
            recorder.record(module.CoverageEvent.REQUESTED, oid_value)
            recorder.record(module.CoverageEvent.ACQUIRED, reader.returned_oid)
            module._content_hits(
                "clean message", oid_value, finder,
                subject_kind="commit-message",
            )
            recorder.record(module.CoverageEvent.SCANNED, oid_value)
            coverage = recorder.proof()
            if isinstance(coverage, module.Refusal):
                return coverage
            return _empty_history_proof(module, selected), coverage, ()

        async def run_case(*, returned_oid=oid, expected=(oid,), detector_fault=False):
            module._range_selection = mock.AsyncMock(return_value=module.RangeSelection(
                selection.remote,
                selection.destination,
                selection.source,
                selection.tip,
                expected,
                expected,
            ))
            module._acquire_history = acquire
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
                module._acquire_history,
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
            module._range_selection, module._acquire_history,
            module._confirm_tip, module._content_hits,
        )
        module._range_selection = mock.AsyncMock(return_value=module.RangeSelection(
            "origin", "refs/heads/main", "refs/heads/main", "4" * 40,
            expected, expected
        ))
        module._confirm_tip = lambda *_args: None
        module._content_hits = lambda *_args, **_kwargs: []

        async def acquire(selected, _reader, _finder, recorder, _deadline):
            for oid in selected.expected_oids:
                recorder.record(module.CoverageEvent.REQUESTED, oid)
                recorder.record(module.CoverageEvent.ACQUIRED, oid)
                module._content_hits(
                    "clean message", oid, lambda _line: [],
                    subject_kind="commit-message",
                )
                recorder.record(module.CoverageEvent.SCANNED, oid)
            coverage = recorder.proof()
            if isinstance(coverage, module.Refusal):
                return coverage
            return _empty_history_proof(module, selected), coverage, ()

        module._acquire_history = acquire

        def run(transform, selection_oids=expected):
            module._range_selection = mock.AsyncMock(return_value=module.RangeSelection(
                "origin", "refs/heads/main", "refs/heads/main", "4" * 40,
                selection_oids, selection_oids,
            ))
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
                    self.assertNotIn("receipt=v3", stdout + stderr)

            duplicate_input, code, stdout, stderr = run(
                lambda event, oid: ((event, oid),), (first, first)
            )
            self.assertEqual(duplicate_input.refusal.failure_id, "PS-MSG-COVERAGE")
            self.assertEqual(code, 2)
            self.assertNotIn("receipt=v3", stdout + stderr)

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
            self.assertEqual(reordered.coverage.scanned_message_oids, independently_observed)
            self.assertEqual(code, 0)
            self.assertIn("commit-set=" + module._commit_set_digest(expected), stdout)
            self.assertEqual(stderr, "")

            clean, code, stdout, stderr = run(lambda event, oid: ((event, oid),))
            self.assertEqual(clean.kind, "clean")
            self.assertEqual(clean.coverage.scanned_message_oids, expected)
            self.assertEqual(code, 0)
            self.assertIn("receipt=v3", stdout)
            self.assertEqual(stderr, "")
        finally:
            (
                module._range_selection, module._acquire_history,
                module._confirm_tip, module._content_hits,
            ) = originals

    def test_r4_actual_boundary_redaction_matrix(self) -> None:
        module = self._module("redaction")
        sentinels = {
            "staged": "R4_STAGE_SENTINEL",
            "path": "R4_PATH_SENTINEL",
            "history": "R4_HISTORY_SENTINEL",
            "subject": "R4_SUBJECT_SENTINEL",
            "body": "R4_BODY_SENTINEL",
            "trailer": "R4_TRAILER_SENTINEL",
            "machine": _join(WIN, BS, USERS, BS, "r4-sentinel-user"),
        }
        subjects = {
            "staged": "tracked-blob", "path": "path-blob", "history": "history-blob",
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
            "origin", "refs/heads/main", "refs/heads/main", "2" * 40,
            (oid,), (oid,)
        )

        class Reader:
            def __init__(self):
                self.reap_certificate = None
                self.state = module.ReaderState.ACTIVE

            async def start(self):
                return None

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
            module._acquire_history,
            module._confirm_tip,
            module._content_hits,
        )
        module._range_selection = mock.AsyncMock(return_value=selection)
        module._confirm_tip = lambda *_args: None

        async def acquire(selected, _reader, finder, recorder, _deadline):
            for selected_oid in selected.expected_oids:
                recorder.record(module.CoverageEvent.REQUESTED, selected_oid)
                recorder.record(module.CoverageEvent.ACQUIRED, selected_oid)
                module._content_hits(
                    "clean message", selected_oid, finder,
                    subject_kind="commit-message",
                )
                recorder.record(module.CoverageEvent.SCANNED, selected_oid)
            coverage = recorder.proof()
            if isinstance(coverage, module.Refusal):
                return coverage
            return _empty_history_proof(module, selected), coverage, ()

        module._acquire_history = acquire

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
            self.assertIn("receipt=v3", output)
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
            self.assertNotIn("receipt=v3", output)

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
                    subject_kind="history-blob",
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
                module._acquire_history,
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
