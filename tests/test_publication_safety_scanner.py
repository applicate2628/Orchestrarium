"""Regression tests for the allowlist-aware publication leak-scanner.

Drives the REAL scanner (`check-publication-safety.sh`, both the Claude and
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
  - fallback (no-Python / allowlist-owner-unreachable): refined-ERE branch still
    BLOCKs real paths + secrets and still PASSes true placeholders, emitting the
    degraded-mode notice.
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

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CODEX_SCANNER = REPO_ROOT / "src.codex" / "skills" / "lead" / "scripts" / "check-publication-safety.sh"
CLAUDE_SCANNER = REPO_ROOT / "src.claude" / "agents" / "scripts" / "check-publication-safety.sh"
CODEX_REF = REPO_ROOT / "src.codex" / "skills" / "lead" / "hooks" / "check-machine-local-path.py"
SCANNERS = (CODEX_SCANNER, CLAUDE_SCANNER)

BACKSLASH = chr(92)  # keep the literal backslash out of source path literals


def _join(*parts: str) -> str:
    """Concatenate fragments with no separator. Used so a complete flaggable
    path is only ever built at runtime, never present as a source literal."""
    return "".join(parts)


def _bash() -> str | None:
    bash = shutil.which("bash")
    if bash and not _is_windows_wsl_bash(bash):
        return bash
    for candidate in _git_bash_candidates():
        if candidate.exists():
            return str(candidate)
    return None if bash and _is_windows_wsl_bash(bash) else bash


def _is_windows_wsl_bash(path: str) -> bool:
    if os.name != "nt":
        return False
    parts = {part.lower() for part in Path(path).parts}
    return Path(path).name.lower() == "bash.exe" and {"windows", "system32"}.issubset(parts)


def _git_bash_candidates() -> list[Path]:
    candidates: list[Path] = []
    git = shutil.which("git")
    if git:
        for parent in Path(git).parents:
            if parent.name.lower() == "git":
                candidates.extend((parent / "bin" / "bash.exe", parent / "usr" / "bin" / "bash.exe"))
                break
    for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(env_name)
        if base:
            candidates.extend((Path(base) / "Git" / "bin" / "bash.exe", Path(base) / "Git" / "usr" / "bin" / "bash.exe"))
    return candidates


def _git() -> str | None:
    return shutil.which("git")


def _load_find_machine_paths():
    spec = importlib.util.spec_from_file_location("_mlp_ref_test", str(CODEX_REF))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.find_machine_paths


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


@unittest.skipIf(_bash() is None or _git() is None, "needs bash + git on PATH")
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
        scanner resolves its allowlist owner via its own absolute BASH_SOURCE, so
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
        git = _git()
        bash = _bash()
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
                [bash, str(scanner)],
                cwd=td,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
            )
            return proc.returncode, proc.stdout

    def _run_cached_nothing_staged(self, scanner: Path) -> tuple[int, str]:
        """Run the scanner in a real repo with NOTHING staged at all -- the
        live-failure shape (2026-07-25/26): after a commit, the index equals
        HEAD, so `git diff --cached` is empty and the scanner examines nothing.
        Distinct from `_run_cached`, which always stages exactly one file."""
        git = _git()
        bash = _bash()
        with tempfile.TemporaryDirectory() as td:
            subprocess.run([git, "init", "-q", td], check=True, capture_output=True)
            subprocess.run([git, "-C", td, "config", "user.email", "t@t"], check=True, capture_output=True)
            subprocess.run([git, "-C", td, "config", "user.name", "t"], check=True, capture_output=True)
            proc = subprocess.run(
                [bash, str(scanner)],
                cwd=td,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            return proc.returncode, proc.stdout

    def test_block_rows_exit_1(self) -> None:
        for scanner in SCANNERS:
            for name, content in block_rows().items():
                with self.subTest(scanner=scanner.parent.parent.name, row=name):
                    self.assertEqual(self._run_cached(scanner, content), 1,
                                     f"{name!r} must BLOCK (exit 1)")

    def test_pass_rows_exit_0(self) -> None:
        for scanner in SCANNERS:
            for name, content in pass_rows().items():
                with self.subTest(scanner=scanner.parent.parent.name, row=name):
                    self.assertEqual(self._run_cached(scanner, content), 0,
                                     f"{name!r} must PASS (exit 0)")

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
                        [_bash(), str(scanner), "--path", str(fixture)],
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
                        [_bash(), str(scanner), "--path", str(fixture_dir)],
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
                        filename="scripts/check-publication-safety.sh",
                    ),
                    1,
                )

    def test_scanner_file_allows_exact_intentional_regex_catalog_lines(self) -> None:
        # Catalog entries assembled per MF6: the marker phrases must never sit
        # contiguously in this tracked source, only in the staged fixture.
        catalog = "\n".join(
            [
                "nonpath_patterns=(",
                _join("  'BEGIN RSA PRIVATE", " KEY'"),
                _join("  'BEGIN OPENSSH PRIVATE", " KEY'"),
                _join("  'BEGIN PRIVATE", " KEY'"),
                _join("  'private", "_key'"),
                _join("  'secret", "_key'"),
                ")",
            ]
        )
        for scanner in SCANNERS:
            with self.subTest(scanner=scanner.parent.parent.name):
                self.assertEqual(
                    self._run_cached(
                        scanner,
                        catalog,
                        filename="scripts/check-publication-safety.sh",
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
                        _join("  'secret", "_key' # ", leak),
                        filename="scripts/check-publication-safety.sh",
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
                    self._run_cached(scanner, content, filename="scripts/check-publication-safety.sh"),
                    0,
                    "scanner source under its own name must PASS (no gate self-block)",
                )
                self.assertEqual(
                    self._run_cached(scanner, content, filename="scripts/some-other-script.sh"),
                    1,
                    "scanner source under any other name must still BLOCK",
                )


class TestPublicationSafetyScannerLauncher(unittest.TestCase):
    def test_windows_launcher_does_not_use_wsl_bash_for_windows_paths(self) -> None:
        if os.name != "nt":
            self.skipTest("Windows-only launcher guard")
        bash = _bash()
        if bash is None:
            self.skipTest("needs Git Bash for Windows-path scanner scripts")
        self.assertFalse(_is_windows_wsl_bash(bash), bash)


@unittest.skipIf(_bash() is None or _git() is None, "needs bash + git on PATH")
class TestPublicationSafetyScannerFallback(unittest.TestCase):
    """Exercise the no-Python / allowlist-owner-unreachable refined-ERE branch.

    The branch fires when BOTH python3/python are unreachable OR the allowlist
    owner module is missing. We trigger it deterministically by pointing PATH at
    an empty shim dir (no python) AND keeping git reachable, which is awkward on
    MSYS; instead we drive the SAME code branch by hiding the reference module
    for the duration via a copied scanner whose sibling hooks dir has no owner.
    Simpler and equivalent: set the marker env the scanner does not read, so we
    use the documented branch trigger — an unreadable owner path — by running a
    scanner copy from a temp dir whose ../hooks/ lacks the owner."""

    def _run_fallback(self, content: str) -> tuple[int, str]:
        git = _git()
        bash = _bash()
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            # Lay out a scanner copy with an EMPTY sibling hooks dir (no owner) ->
            # the `-f "$ref_module"` guard is false -> fallback branch runs. This
            # is the exact same branch as "no python reachable".
            (tdp / "scripts").mkdir()
            (tdp / "hooks").mkdir()
            shutil.copy2(CODEX_SCANNER, tdp / "scripts" / "check-publication-safety.sh")
            repo = tdp / "repo"
            repo.mkdir()
            subprocess.run([git, "init", "-q", str(repo)], check=True, capture_output=True)
            subprocess.run([git, "-C", str(repo), "config", "user.email", "t@t"], check=True, capture_output=True)
            subprocess.run([git, "-C", str(repo), "config", "user.name", "t"], check=True, capture_output=True)
            (repo / "fixture.txt").write_text(content + "\n", encoding="utf-8")
            subprocess.run([git, "-C", str(repo), "add", "fixture.txt"], check=True, capture_output=True)
            proc = subprocess.run(
                [bash, str(tdp / "scripts" / "check-publication-safety.sh")],
                cwd=str(repo),
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            return proc.returncode, proc.stderr

    def test_fallback_blocks_real_path(self) -> None:
        rc, err = self._run_fallback(_join(WIN, BS, USERS, BS, REAL))
        self.assertEqual(rc, 1, f"fallback must BLOCK a real path; stderr={err!r}")
        self.assertIn("refined regex fallback", err)

    def test_fallback_blocks_dev_root(self) -> None:
        rc, err = self._run_fallback(_join(WIN_D, BS, DEV, BS, "Orchestrator", BS, "Orchestrarium"))
        self.assertEqual(rc, 1, f"fallback must BLOCK a dev root; stderr={err!r}")

    def test_fallback_blocks_secret(self) -> None:
        rc, err = self._run_fallback("pass" + "word" + ": hunter2")
        self.assertEqual(rc, 1, f"fallback must still BLOCK a secret (MF3); stderr={err!r}")

    def test_fallback_passes_placeholder(self) -> None:
        rc, err = self._run_fallback(_join(WIN, BS, USERS, BS, "<name>"))
        self.assertEqual(rc, 0, f"fallback must PASS an angle-bracket placeholder; stderr={err!r}")

    def test_fallback_passes_env_var(self) -> None:
        rc, err = self._run_fallback("%USER" + "PROFILE%")
        self.assertEqual(rc, 0, f"fallback must PASS an env-var placeholder; stderr={err!r}")


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
