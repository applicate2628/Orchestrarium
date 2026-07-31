"""Regression tests for the two anti-decay hooks added 2026-07-17.

Both target the operator's report that always-on postures decay: *"постоянно забывают
использовать mcp ... потом снова сваливаются после остановок"*. The split between them
is load-bearing and was corrected by first-person evidence mid-build (see the
`reminders-decay-by-surface` work-item):

  * `turn-anchor-reminder` (UserPromptSubmit) re-anchors TURN-BOUNDARY postures — "a
    passed slice is not completion" — at the start of every turn. It fires at turn start,
    so it CANNOT reach a mid-turn failure; that is by design, not a gap.
  * `check-mcp-momentum` (PreToolUse Grep|Bash, AUDIT) fires at the mid-turn TOOL CHOICE,
    the moment MCP momentum actually lapses (~100 successful shell calls, next tool picked
    from momentum not from a rule sitting in context). It nudges ONLY on code-navigation
    shapes, ONLY when a code-intelligence MCP is actually configured, and never blocks --
    always exits 0, delivering a nudge via `hookSpecificOutput.additionalContext` on
    stdout (see `hook_common.emit_advisory`) rather than the stderr-plus-exit-1 form
    measured to reach nobody (work-items/bugs/2026-07-26-mcp-reminder-uses-the-once-
    per-session-form-its-sibling-calls-broken.md).

These were untested when shipped — the exact gap that let the `bugfix-discipline`
isCompactSummary false positive live undetected. The bar here is the one that FP taught:
exercise the real envelope, both the fire and the silence.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.bash_runtime import resolve_bash

BASH = resolve_bash()

REPO_ROOT = Path(__file__).resolve().parent.parent
MCP_HOOK = REPO_ROOT / "scripts" / "universal-hooks" / "hooks" / "check-mcp-momentum.py"
MCP_POLICY = REPO_ROOT / "scripts" / "universal-hooks" / "scripts" / "mcp_continuity_policy.py"
MCP_REMINDER_PY = REPO_ROOT / "scripts" / "universal-hooks" / "scripts" / "mcp-usage-reminder.py"
TURN_ANCHOR_SH = REPO_ROOT / "scripts" / "universal-hooks" / "scripts" / "turn-anchor-reminder.sh"
TURN_ANCHOR_PY = REPO_ROOT / "scripts" / "universal-hooks" / "scripts" / "turn-anchor-reminder.py"


def run_hook(script: Path, envelope: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(envelope, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


class McpContinuityContract(unittest.TestCase):
    def test_one_policy_source_and_exactly_three_thin_python_consumers(self) -> None:
        self.assertTrue(MCP_POLICY.is_file(), "missing canonical MCP continuity policy")
        canon_root = REPO_ROOT / "scripts" / "universal-hooks"
        consumers: set[Path] = set()
        for candidate in (*canon_root.glob("scripts/*.py"), *canon_root.glob("hooks/*.py")):
            tree = ast.parse(candidate.read_text(encoding="utf-8"))
            if any(
                isinstance(node, ast.ImportFrom)
                and node.module == "mcp_continuity_policy"
                for node in ast.walk(tree)
            ):
                consumers.add(candidate)
        self.assertEqual(consumers, {MCP_REMINDER_PY, TURN_ANCHOR_PY, MCP_HOOK})

        forbidden_restatements = (
            "[MCP / tools reminder",
            "[mcp-momentum AUDIT]",
            "CODE_INTEL_HINTS",
            "CODE_PATTERN_RE",
            "SHELL_TREE_SEARCH_RE",
            '"work-items/"',
            '".reports/"',
            '".plans/"',
            '".scratch/"',
        )
        for consumer in consumers:
            text = consumer.read_text(encoding="utf-8")
            with self.subTest(consumer=consumer.name):
                for fragment in forbidden_restatements:
                    self.assertNotIn(fragment, text)


class TestMcpMomentumDiscrimination(unittest.TestCase):
    """AUDIT hook: it must ALWAYS exit 0 and never write to stderr, and it must warn
    (via stdout JSON) on exactly the navigation shapes and stay silent on everything
    else. A nudge that fires on every read is noise, and noise trains the reader to
    ignore the whole class."""

    def setUp(self) -> None:
        # The hook only nudges when a code-intelligence MCP is actually configured for
        # this user. Point it at a synthetic config so the test does not depend on the
        # developer's real ~/.claude.json (which may or may not have one).
        self._home = tempfile.mkdtemp()
        (Path(self._home) / ".claude.json").write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "codegraph": {"command": "SECRET-COMMAND"},
                        "language-server": {"token": "TOP-SECRET"},
                        "lsp-local": {},
                        "repomix": {},
                        "serena": {},
                        "time": {},
                    }
                }
            ),
            encoding="utf-8",
        )
        self._env = dict(os.environ)
        self._env["HOME"] = self._home
        self._env["USERPROFILE"] = self._home

    def tearDown(self) -> None:
        shutil.rmtree(self._home, ignore_errors=True)

    def _run(self, envelope: dict) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(MCP_HOOK)],
            input=json.dumps(envelope, ensure_ascii=False),
            capture_output=True, text=True, encoding="utf-8", env=self._env,
        )

    def assert_nudges(self, envelope: dict, should_nudge: bool) -> None:
        result = self._run(envelope)
        # AUDIT hook never BLOCKS (never exit 2) and never uses a non-zero exit
        # for a nudge either -- the advisory travels via stdout JSON, always
        # exit 0 (see hook_common.emit_advisory).
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        fired = "mcp-momentum" in result.stdout
        self.assertEqual(fired, should_nudge, result.stdout or "(no stdout)")
        if should_nudge:
            self.assertEqual(len(result.stdout.splitlines()), 1)
            payload = json.loads(result.stdout)
            self.assertEqual(set(payload), {"hookSpecificOutput"})
            specific = payload["hookSpecificOutput"]
            self.assertEqual(
                set(specific), {"hookEventName", "additionalContext"}
            )
            self.assertEqual(specific["hookEventName"], "PreToolUse")
            self.assertNotIn("SECRET-COMMAND", result.stdout)
            self.assertNotIn("TOP-SECRET", result.stdout)
            self.assertIn("(+2 more)", specific["additionalContext"])

    def test_mcp_continuity_current_host_shape_matrix(self) -> None:
        positives = (
            ("native-grep", "Grep", {"pattern": "def parse_config"}),
            ("bash", "Bash", {"command": "rg -n 'def parse_config' src/"}),
            ("powershell", "PowerShell", {"command": "ag 'class Parser' scripts/"}),
            ("shell-command", "shell_command", {"command": "ack 'references' app/"}),
            ("exec-cmd", "exec_command", {"cmd": "rg -n 'def parse_config'"}),
            ("exec-command", "exec_command", {"command": "rg --files src/"}),
            ("ordinary-rg", "Bash", {"command": "rg -n 'class Parser' src/"}),
            ("ag-default-recursion", "Bash", {"command": "ag 'def parse_config'"}),
            ("ack-default-recursion", "Bash", {"command": "ack 'def parse_config'"}),
            ("recursive-grep", "Bash", {"command": "grep -Rn 'class Parser' src/"}),
            ("no-explicit-path", "Bash", {"command": "rg -n 'def parse_config'"}),
            ("source-root", "Bash", {"command": "rg -n handler lib/"}),
            ("source-glob", "Bash", {"command": "rg -g '*.py' handler"}),
            ("mixed-scope", "Bash", {"command": "rg -n 'def parse_config' work-items/ src/"}),
            ("lookalike-not-exempt", "Bash", {"command": "rg -n 'def parse_config' tmp/work-items-copy/"}),
        )
        for name, tool_name, tool_input in positives:
            with self.subTest(name=name):
                self.assert_nudges(
                    {"tool_name": tool_name, "tool_input": tool_input}, True
                )

    def test_mcp_continuity_negative_discrimination_matrix(self) -> None:
        repo = Path(self._home) / "negative-coordinate-repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        negatives = (
            ("known-file", "Grep", {"pattern": "TODO", "path": "README.md"}),
            ("known-file-read", "PowerShell", {"command": "Get-Content scripts/install-codex.ps1"}),
            ("docs-prose", "Bash", {"command": "rg -n installation docs/"}),
            ("pytest", "shell_command", {"command": "python -m pytest tests/ -q"}),
            ("nonrecursive-grep", "exec_command", {"cmd": "grep 'def parse' src/parser.py"}),
            ("work-items", "Bash", {"command": "rg -n 'def parse_config' work-items/"}),
            ("reports", "Bash", {"command": "rg -n 'def parse_config' .reports/"}),
            ("plans", "Bash", {"command": "rg -n 'def parse_config' .plans/"}),
            ("scratch", "Bash", {"command": "rg -n 'def parse_config' .scratch/"}),
        )
        for name, tool_name, tool_input in negatives:
            with self.subTest(name=name):
                self.assert_nudges(
                    {
                        "cwd": str(repo),
                        "tool_name": tool_name,
                        "tool_input": tool_input,
                    },
                    False,
                )

    def test_mcp_exemptions_are_repository_rooted_not_segment_rooted(self) -> None:
        repo = Path(self._home) / "nested-token-repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        cases = (
            (
                "bash-rg",
                {"tool_name": "Bash", "tool_input": {"command": "rg -n 'def parse_config' scripts/work-items"}},
            ),
            (
                "native-grep",
                {"tool_name": "Grep", "tool_input": {"pattern": "def parse_config", "path": "scripts/work-items"}},
            ),
            (
                "bash-rg-files",
                {"tool_name": "Bash", "tool_input": {"command": "rg --files scripts/work-items"}},
            ),
            (
                "exec-command-cmd",
                {"tool_name": "exec_command", "tool_input": {"cmd": "rg -n 'def parse_config' scripts/work-items"}},
            ),
        )
        for name, envelope in cases:
            envelope["cwd"] = str(repo)
            with self.subTest(name=name):
                self.assert_nudges(envelope, True)

    def test_mcp_exemption_coordinate_normalization_matrix(self) -> None:
        module_name = "mcp_continuity_policy_coordinate_test"
        spec = importlib.util.spec_from_file_location(module_name, MCP_POLICY)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        policy = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = policy
        spec.loader.exec_module(policy)
        self.addCleanup(sys.modules.pop, module_name, None)

        rows: list[tuple[str, str, str, str, bool]] = []
        for subtree in ("work-items", ".reports", ".plans", ".scratch"):
            rows.extend(
                (
                    (f"{subtree}-relative", "/repo", "/repo", subtree, True),
                    (f"{subtree}-dot-relative", "/repo", "/repo", f"./{subtree}/item", True),
                    (f"{subtree}-absolute", "/repo", "/repo", f"/repo/{subtree}/item", True),
                )
            )
        rows.extend(
            (
                ("nested-cwd-local-token", "/repo", "/repo/scripts", "work-items", False),
                ("nested-cwd-parent", "/repo", "/repo/scripts", "../work-items/x", True),
                ("repeated-separators", "/repo", "/repo", "/repo//work-items///x", True),
                ("dot-components", "/repo", "/repo", "./.reports/./x", True),
                ("dot-dot-inside", "/repo", "/repo", ".plans/a/../b", True),
                ("dot-dot-leaves-exempt", "/repo", "/repo", ".scratch/../scripts", False),
                ("dot-dot-leaves-repository", "/repo", "/repo", "work-items/../../outside", False),
                ("component-lookalike", "/repo", "/repo", "work-items-copy", False),
                ("nested-token", "/repo", "/repo", "tmp/work-items", False),
                ("repository-root", "/repo", "/repo", ".", False),
                ("windows-relative-case", r"C:\Repo", r"C:\Repo", r"WORK-ITEMS\x", True),
                ("windows-mixed-separators", r"C:\Repo", r"c:\repo", "c:/REPO/work-items/x", True),
                ("windows-nested-parent", r"C:\Repo", r"C:\Repo\scripts", r"..\work-items\x", True),
                ("windows-different-drive", r"C:\Repo", r"C:\Repo", r"D:\Repo\work-items\x", False),
                ("windows-drive-relative", r"C:\Repo", r"C:\Repo", r"C:work-items\x", False),
                ("windows-unc-same-anchor", r"\\server\share\repo", r"\\SERVER\SHARE\repo", r"\\server\share\repo\work-items\x", True),
                ("windows-unc-different-anchor", r"\\server\share\repo", r"\\server\share\repo", r"\\server\other\repo\work-items\x", False),
                ("posix-exact-case", "/Repo", "/Repo", "/Repo/work-items/x", True),
                ("posix-case-mismatch", "/Repo", "/Repo", "/repo/work-items/x", False),
                ("posix-outside-root", "/repo", "/repo", "/other/work-items/x", False),
            )
        )
        self.assertEqual(len(rows), 32)
        for name, root, cwd, scope, expected in rows:
            flavor = "windows" if root.startswith(("C:", "c:", "\\\\")) else "posix"
            with self.subTest(name=name):
                coordinate = policy._ScopeCoordinate.from_paths(root, cwd, flavor)
                self.assertIsNotNone(coordinate)
                self.assertEqual(policy._scope_is_exempt(scope, coordinate), expected)

        sentinel = Path(self._home) / "coordinate-side-effect-sentinel"
        sentinel.write_text("unchanged", encoding="utf-8")
        unavailable_rows = (
            ("missing-cwd", None),
            ("empty-cwd", ""),
            ("non-string-cwd", 7),
            ("non-absolute-cwd", "repo/scripts"),
            ("missing-git-marker", self._home),
            ("malformed-drive-relative", r"C:repo\scripts"),
        )
        for name, raw_cwd in unavailable_rows:
            with self.subTest(name=name):
                self.assertIsNone(policy._ScopeCoordinate.from_cwd(raw_cwd))
        with self.subTest(name="path-flavor-mismatch"):
            self.assertIsNone(policy._ScopeCoordinate.from_paths(r"C:\Repo", "/Repo", "windows"))
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "unchanged")

        policy_tree = ast.parse(MCP_POLICY.read_text(encoding="utf-8"))
        self.assertFalse(
            any(
                isinstance(node, (ast.Import, ast.ImportFrom))
                and any(alias.name == "subprocess" for alias in node.names)
                for node in ast.walk(policy_tree)
            )
        )
        coordinate_nodes = tuple(
            node
            for node in policy_tree.body
            if (
                isinstance(node, ast.ClassDef) and node.name == "_ScopeCoordinate"
            )
            or (
                isinstance(node, ast.FunctionDef)
                and node.name in {"_scope_is_exempt", "_all_scopes_are_exempt"}
            )
        )
        self.assertFalse(
            any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"resolve", "expanduser", "glob", "rglob"}
                for owner in coordinate_nodes
                for node in ast.walk(owner)
            )
        )

    def test_mcp_exemption_cross_tool_all_scopes_matrix(self) -> None:
        repo = Path(self._home) / "cross-tool-repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        cwd = str(repo)
        absolute_exempt = str(repo / "work-items" / "x")
        shell_rows = (
            ("bash-all", "Bash", "command", "rg -n 'def parse' work-items .reports", False),
            ("bash-mixed", "Bash", "command", "rg -n 'def parse' work-items scripts", True),
            ("bash-unresolvable", "Bash", "command", "rg -n 'def parse' work-items '$UNEXPANDED'", True),
            ("powershell-all", "PowerShell", "command", "rg -n 'def parse' .plans .scratch", False),
            ("powershell-mixed", "PowerShell", "command", "rg -n 'def parse' .plans src", True),
            ("powershell-unresolvable", "PowerShell", "command", "rg -n 'def parse' .plans '%UNEXPANDED%'", True),
            ("shell-command-all", "shell_command", "command", "rg -n 'def parse' work-items .scratch", False),
            ("shell-command-mixed", "shell_command", "command", "rg -n 'def parse' work-items app", True),
            ("shell-command-unresolvable", "shell_command", "command", "rg -n 'def parse' work-items '~'", True),
            ("exec-command-all", "exec_command", "cmd", "rg -n 'def parse' work-items .reports", False),
            ("exec-command-mixed", "exec_command", "cmd", "rg -n 'def parse' work-items scripts", True),
            ("exec-command-unresolvable", "exec_command", "cmd", "rg -n 'def parse' work-items '${UNEXPANDED}'", True),
        )
        for name, tool_name, key, command, expected in shell_rows:
            with self.subTest(name=name):
                self.assert_nudges(
                    {"cwd": cwd, "tool_name": tool_name, "tool_input": {key: command}},
                    expected,
                )

        surface_rows = (
            ("grep-exempt", "Grep", {"pattern": "def parse", "path": "work-items"}, False),
            ("grep-nested-token", "Grep", {"pattern": "def parse", "path": "scripts/work-items"}, True),
            ("rg-exempt", "Bash", {"command": "rg -n 'def parse' work-items"}, False),
            ("rg-nested-token", "Bash", {"command": "rg -n 'def parse' scripts/work-items"}, True),
            ("ag-exempt", "Bash", {"command": "ag 'def parse' .reports"}, False),
            ("ag-nested-token", "Bash", {"command": "ag 'def parse' scripts/.reports"}, True),
            ("ack-exempt", "Bash", {"command": "ack 'def parse' .plans"}, False),
            ("ack-nested-token", "Bash", {"command": "ack 'def parse' scripts/.plans"}, True),
            ("grep-recursive-exempt", "Bash", {"command": "grep -Rn 'def parse' .scratch"}, False),
            ("grep-recursive-nested-token", "Bash", {"command": "grep -Rn 'def parse' scripts/.scratch"}, True),
            ("rg-files-exempt", "Bash", {"command": "rg --files work-items"}, False),
            ("rg-files-nested-token", "Bash", {"command": "rg --files scripts/work-items"}, True),
        )
        for name, tool_name, tool_input, expected in surface_rows:
            with self.subTest(name=name):
                self.assert_nudges(
                    {"cwd": cwd, "tool_name": tool_name, "tool_input": tool_input},
                    expected,
                )

        directory_change_rows = (
            ("relative-after-cd", "cd scripts && rg -n 'def parse' work-items", True),
            ("absolute-after-cd", f"cd scripts && rg -n 'def parse' '{absolute_exempt}'", False),
        )
        for name, command, expected in directory_change_rows:
            with self.subTest(name=name):
                self.assert_nudges(
                    {"cwd": cwd, "tool_name": "Bash", "tool_input": {"command": command}},
                    expected,
                )

    def test_rg_files_selector_values_are_not_scopes(self) -> None:
        repo = Path(self._home) / "rg-files-selector-repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        rows = (
            ("short-rooted", "rg --files -g '*.py' work-items", False),
            ("long-rooted", "rg --files --glob '*.py' work-items", False),
            (
                "short-source-looking-selector",
                "rg --files -g 'src/**/*.py' work-items",
                False,
            ),
            (
                "long-source-looking-selector",
                "rg --files --glob 'scripts/work-items/**/*.py' work-items",
                False,
            ),
            (
                "equals-rooted-control",
                "rg --files --glob='src/**/*.py' work-items",
                False,
            ),
            ("short-nested-control", "rg --files -g '*.py' scripts/work-items", True),
            (
                "long-nested-control",
                "rg --files --glob '*.py' scripts/work-items",
                True,
            ),
            ("short-mixed-control", "rg --files -g '*.py' work-items src", True),
            (
                "long-mixed-control",
                "rg --files --glob '*.py' .reports scripts",
                True,
            ),
            ("no-explicit-scope-control", "rg --files -g '*.py'", True),
        )
        self.assertEqual(len(rows), 10)
        for name, command, expected in rows:
            with self.subTest(name=name):
                self.assert_nudges(
                    {
                        "cwd": str(repo),
                        "tool_name": "Bash",
                        "tool_input": {"command": command},
                    },
                    expected,
                )

    def test_rg_files_uses_shared_search_parts_option_grammar(self) -> None:
        tree = ast.parse(MCP_POLICY.read_text(encoding="utf-8"))
        functions = {
            node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
        }
        search_parts = functions["_search_parts"]
        shell_search = functions["_shell_search_is_navigation"]

        grammar_owners = tuple(
            owner.name
            for owner in functions.values()
            if any(
                isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Load)
                and node.id == "OPTIONS_WITH_VALUES"
                for node in ast.walk(owner)
            )
        )
        self.assertEqual(grammar_owners, ("_search_parts",))

        search_parts_calls = tuple(
            node
            for node in ast.walk(shell_search)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_search_parts"
        )
        self.assertEqual(len(search_parts_calls), 1)
        files_branches = tuple(
            node
            for node in shell_search.body
            if isinstance(node, ast.If)
            and any(
                marker in ast.unparse(node.test) for marker in ("--files", "files_mode")
            )
        )
        self.assertEqual(len(files_branches), 1)
        files_branch = files_branches[0]

        branch_nodes = tuple(
            nested for statement in files_branch.body for nested in ast.walk(statement)
        )
        branch_names = {
            node.id
            for node in branch_nodes
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        }
        option_literals = {
            node.value
            for node in ast.walk(shell_search)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        violations = []
        if "args" in branch_names:
            violations.append("rg --files branch rescans raw args")
        if "scopes" not in branch_names:
            violations.append("rg --files branch does not consume parsed scopes")
        if search_parts_calls[0].lineno > files_branch.lineno:
            violations.append("_search_parts runs after the rg --files branch")
        if "files_mode" not in ast.unparse(search_parts_calls[0]):
            violations.append("_search_parts is not told that rg --files has no query operand")
        duplicate_options = option_literals.intersection(
            {"-g", "--glob", "--type", "-t", "--include", "--exclude", "--iglob"}
        )
        if duplicate_options:
            violations.append(f"duplicate selector option grammar: {sorted(duplicate_options)}")
        self.assertEqual(
            violations,
            [],
            "_search_parts must solely own rg --files selector/scope parsing: "
            + "; ".join(violations),
        )
        self.assertIn("files_mode", {argument.arg for argument in search_parts.args.args})

    def test_mcp_adapter_forwards_raw_cwd_without_policy_duplication(self) -> None:
        tree = ast.parse(MCP_HOOK.read_text(encoding="utf-8"))
        main = next(
            node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main"
        )
        classify_calls = (
            node
            for node in ast.walk(main)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "classify_tool_choice"
        )
        classify_calls = tuple(classify_calls)
        self.assertEqual(len(classify_calls), 1)
        call = classify_calls[0]
        self.assertEqual(len(call.args), 3)
        raw_cwd = call.args[2]
        self.assertIsInstance(raw_cwd, ast.Call)
        self.assertIsInstance(raw_cwd.func, ast.Attribute)
        self.assertIsInstance(raw_cwd.func.value, ast.Name)
        self.assertEqual(raw_cwd.func.value.id, "envelope")
        self.assertEqual(raw_cwd.func.attr, "get")
        self.assertEqual(len(raw_cwd.args), 1)
        self.assertIsInstance(raw_cwd.args[0], ast.Constant)
        self.assertEqual(raw_cwd.args[0].value, "cwd")

        adapter_source = ast.unparse(main)
        for forbidden in (
            ".git",
            "resolve(",
            "casefold(",
            "EXEMPT_SCOPE_SEGMENTS",
            "_ScopeCoordinate",
            "_scope_is_exempt",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, adapter_source)

    def test_mcp_momentum_agent_id_uses_same_warn_only_policy(self) -> None:
        for should_nudge, tool_input in (
            (True, {"command": "rg -n 'def parse_config' src/"}),
            (False, {"command": "rg -n installation docs/"}),
        ):
            root = self._run({"tool_name": "Bash", "tool_input": tool_input})
            agent = self._run(
                {
                    "agent_id": "synthetic-agent",
                    "tool_name": "Bash",
                    "tool_input": tool_input,
                }
            )
            with self.subTest(should_nudge=should_nudge):
                self.assertEqual(root.returncode, 0, root.stderr)
                self.assertEqual(agent.returncode, 0, agent.stderr)
                self.assertNotEqual(root.returncode, 2)
                self.assertNotEqual(agent.returncode, 2)
                self.assertEqual(bool(root.stdout), should_nudge)
                self.assertEqual(bool(agent.stdout), should_nudge)

    def test_no_code_intel_server_configured_stays_silent(self) -> None:
        # A nudge on a machine without a code-intelligence MCP would be a lie.
        home = tempfile.mkdtemp()
        (Path(home) / ".claude.json").write_text(
            json.dumps({"mcpServers": {"time": {}, "fetch": {}}}), encoding="utf-8"
        )
        env = dict(os.environ); env["HOME"] = home; env["USERPROFILE"] = home
        result = subprocess.run(
            [sys.executable, str(MCP_HOOK)],
            input=json.dumps({"tool_name": "Grep", "tool_input": {"pattern": "def parse_config"}}),
            capture_output=True, text=True, encoding="utf-8", env=env,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertNotIn("mcp-momentum", result.stdout)
        shutil.rmtree(home, ignore_errors=True)

    def test_malformed_envelope_fails_open(self) -> None:
        result = subprocess.run(
            [sys.executable, str(MCP_HOOK)],
            input="not json at all", capture_output=True, text=True, encoding="utf-8", env=self._env,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    # --- Codex-awareness (2nd-round fix): the hook must not be silently inert
    # on the Codex pack it also ships into. Codex stores MCP config in
    # ~/.codex/config.toml under [mcp_servers.<name>] TOML tables (verified:
    # https://learn.chatgpt.com/codex/extend/mcp), not Claude's ~/.claude.json.
    # Codex's shell tool_name is "Bash" too (verified via the Codex hooks
    # reference), so these drive the already-working Bash branch.

    def test_codex_config_toml_mcp_server_nudges(self) -> None:
        home = tempfile.mkdtemp()
        codex_dir = Path(home) / ".codex"
        codex_dir.mkdir()
        (codex_dir / "config.toml").write_text(
            '[mcp_servers.codegraph]\ncommand = "codegraph-server"\n',
            encoding="utf-8",
        )
        env = dict(os.environ); env["HOME"] = home; env["USERPROFILE"] = home
        result = subprocess.run(
            [sys.executable, str(MCP_HOOK)],
            input=json.dumps({"tool_name": "Bash", "tool_input": {"command": "grep -rn 'class Foo' src/ --include=*.py"}}),
            capture_output=True, text=True, encoding="utf-8", env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertIn("mcp-momentum", result.stdout)
        self.assertIn("codegraph", result.stdout)
        shutil.rmtree(home, ignore_errors=True)

    def test_codex_config_toml_without_code_intel_server_stays_silent(self) -> None:
        home = tempfile.mkdtemp()
        codex_dir = Path(home) / ".codex"
        codex_dir.mkdir()
        (codex_dir / "config.toml").write_text(
            '[mcp_servers.time]\ncommand = "time-server"\n',
            encoding="utf-8",
        )
        env = dict(os.environ); env["HOME"] = home; env["USERPROFILE"] = home
        result = subprocess.run(
            [sys.executable, str(MCP_HOOK)],
            input=json.dumps({"tool_name": "Bash", "tool_input": {"command": "grep -rn 'class Foo' src/ --include=*.py"}}),
            capture_output=True, text=True, encoding="utf-8", env=env,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertNotIn("mcp-momentum", result.stdout)
        shutil.rmtree(home, ignore_errors=True)

    def test_malformed_codex_config_toml_fails_open(self) -> None:
        home = tempfile.mkdtemp()
        codex_dir = Path(home) / ".codex"
        codex_dir.mkdir()
        (codex_dir / "config.toml").write_text("not valid toml [[[", encoding="utf-8")
        env = dict(os.environ); env["HOME"] = home; env["USERPROFILE"] = home
        result = subprocess.run(
            [sys.executable, str(MCP_HOOK)],
            input=json.dumps({"tool_name": "Bash", "tool_input": {"command": "grep -rn 'class Foo' src/ --include=*.py"}}),
            capture_output=True, text=True, encoding="utf-8", env=env,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.stdout, "")
        shutil.rmtree(home, ignore_errors=True)


class TestTurnAnchorEmitsValidContext(unittest.TestCase):
    """The hook's whole job is to emit a UserPromptSubmit additionalContext payload every
    turn. If the JSON is malformed the harness drops it silently, so the payload shape is
    the contract."""

    def test_turn_anchor_python_uses_policy_owned_mcp_context(self) -> None:
        self.assertTrue(MCP_POLICY.is_file(), f"missing {MCP_POLICY}")
        spec = importlib.util.spec_from_file_location(
            "mcp_continuity_policy_turn_anchor_test", MCP_POLICY
        )
        assert spec is not None and spec.loader is not None
        policy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(policy)
        result = subprocess.run(
            [sys.executable, str(TURN_ANCHOR_PY)],
            input="",
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(context, policy.TURN_ANCHOR_CONTEXT)
        self.assertIn("MCP", context)

    @unittest.skipUnless(BASH, "no bash on PATH; the .ps1 sibling covers Windows shells")
    def test_sh_emits_wellformed_userpromptsubmit_context(self) -> None:
        result = subprocess.run(
            [BASH, TURN_ANCHOR_SH.as_posix()],
            input="", capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, "must fail open / exit 0")
        payload = json.loads(result.stdout)
        out = payload["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "UserPromptSubmit")
        # The anchor's load-bearing sentence must actually be present.
        self.assertIn("passed slice is not completion", out["additionalContext"])
        self.assertIn("next unchecked action", out["additionalContext"])

    def test_turn_anchor_never_exits_two(self) -> None:
        for stdin_text in ("", "not json", "x" * 1_000_000):
            with self.subTest(size=len(stdin_text)):
                result = subprocess.run(
                    [sys.executable, str(TURN_ANCHOR_PY)],
                    input=stdin_text,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotEqual(result.returncode, 2)
                self.assertEqual(result.stderr, "")
                payload = json.loads(result.stdout)
                self.assertEqual(
                    payload["hookSpecificOutput"]["hookEventName"],
                    "UserPromptSubmit",
                )
                result.stdout.encode("ascii")

    @unittest.skipUnless(BASH, "bash is required to compare the canonical shell payload")
    def test_turn_anchor_py_matches_sh_text(self) -> None:
        python_result = subprocess.run(
            [sys.executable, str(TURN_ANCHOR_PY)],
            input="",
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        shell_result = subprocess.run(
            [BASH, TURN_ANCHOR_SH.as_posix()],
            input="",
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(python_result.returncode, 0, python_result.stderr)
        self.assertEqual(shell_result.returncode, 0, shell_result.stderr)
        python_context = json.loads(python_result.stdout)["hookSpecificOutput"][
            "additionalContext"
        ]
        shell_context = json.loads(shell_result.stdout)["hookSpecificOutput"][
            "additionalContext"
        ]
        self.assertEqual(python_context.encode("utf-8"), shell_context.encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
