from __future__ import annotations

import importlib.util
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import ast
import hashlib
from collections import Counter
from pathlib import Path
from unittest import mock

from git_push_gate_target import GateTarget, target_for


ROOT = Path(__file__).resolve().parents[1]
CANON_DIR = ROOT / "scripts" / "universal-hooks" / "scripts"
SCRIPT_DIRS = (
    CANON_DIR,
    ROOT / "src.codex" / "skills" / "lead" / "scripts",
    ROOT / "src.claude" / "agents" / "scripts",
)
POLICY_NAME = "check-git-push-gate.py"
RUNNER_NAME = "check-git-push-gate-runner.py"
EXPECTED_FAILURE_ID = "PRG-RUNNER-UNAVAILABLE"
TARGETS = tuple(
    target_for(label, directory)
    for label, directory in zip(("canonical", "codex", "claude"), SCRIPT_DIRS)
)

FORMER_EVALUATE_PUSH_SHA256 = (
    "809BB1D56E0C381738D5E098483115A8716BB73268B45CA4B46E65A0EF6C0BFC"
)
FORMER_PATH_INVENTORY = (
    *(('return', row) for row in (
        'subagent-allow', 'non-dict-allow', 'missing-command-allow',
        'non-push-allow', 'dry-run-allow', 'approval-allow',
        'active-pr-result', 'generic-scan-allow', 'no-allow-deny',
    )),
    *(('raise', row) for row in (
        'parse-uncertain', 'missing-transcript', 'history-unavailable',
        'malformed-pr-authorization', 'inadmissible-generic-grammar',
    )),
)

PREFLIGHT_REASON_BRANCHES = {
    "PFP-ALLOW-SUBAGENT": ("ALLOW_FINAL", "NONE"),
    "PFP-ALLOW-NO-COMMAND": ("ALLOW_FINAL", "NONE"),
    "PFP-ALLOW-NON-PUSH": ("ALLOW_FINAL", "NONE"),
    "PFP-ALLOW-DRY-RUN": ("ALLOW_FINAL", "NONE"),
    "PFP-ALLOW-USER-APPROVED": ("ALLOW_FINAL", "NONE"),
    "PFP-ALLOW-MALFORMED": ("ALLOW_FINAL", "NONE"),
    "PFP-DENY-PARSE": ("DEFER", "RENDER_DENY"),
    "PFP-DENY-TRANSCRIPT": ("DEFER", "RENDER_DENY"),
    "PFP-DENY-KNOWN": ("DEFER", "RENDER_DENY"),
    "PFP-DENY-INTERNAL": ("DEFER", "RENDER_DENY"),
    "PFP-HEAVY": ("DEFER", "EVALUATE_HEAVY"),
}
PREFLIGHT_REASON_PRESENT_FIELDS = {
    "PFP-ALLOW-SUBAGENT": frozenset(),
    "PFP-ALLOW-NO-COMMAND": frozenset(),
    "PFP-ALLOW-NON-PUSH": frozenset(("command", "dialect", "parsed")),
    "PFP-ALLOW-DRY-RUN": frozenset(("command", "dialect", "parsed")),
    "PFP-ALLOW-USER-APPROVED": frozenset((
        "command", "dialect", "transcript_path", "parsed",
        "current_turn_status", "generic_decision",
    )),
    "PFP-ALLOW-MALFORMED": frozenset(),
    "PFP-DENY-PARSE": frozenset(("command", "dialect", "parsed", "failure_id")),
    "PFP-DENY-TRANSCRIPT": frozenset(("command", "dialect", "parsed", "failure_id")),
    "PFP-DENY-KNOWN": frozenset(("failure_id",)),
    "PFP-DENY-INTERNAL": frozenset(),
    "PFP-HEAVY": frozenset((
        "command", "dialect", "transcript_path", "parsed",
        "current_turn_status", "generic_decision", "repository_workdir",
        "repository_workdir_source",
    )),
}

FORMER_EXECUTABLE_ROWS = (
    ("return", "subagent-allow", "preflight", {"agent_id": "subagent"}, None),
    ("return", "non-dict-allow", "preflight", {"tool_input": "bad"}, None),
    ("return", "missing-command-allow", "preflight", {"tool_input": {}}, None),
    ("return", "non-push-allow", "preflight", {"tool_name": "Bash", "tool_input": {"command": "echo safe"}}, None),
    ("return", "dry-run-allow", "preflight", {"tool_name": "Bash", "tool_input": {"command": "git push --dry-run origin main"}}, None),
    ("return", "approval-allow", "preflight", None, "approved"),
    ("return", "active-pr-result", "heavy", None, "active-pr"),
    ("return", "generic-scan-allow", "heavy", None, "generic-scan"),
    ("return", "no-allow-deny", "heavy", None, "plain-deny"),
    ("raise", "parse-uncertain", "preflight", {"tool_name": "Bash", "tool_input": {"command": "env 1=x"}}, None),
    ("raise", "missing-transcript", "preflight", {"tool_name": "Bash", "tool_input": {"command": "git push origin main"}}, None),
    ("raise", "history-unavailable", "heavy", None, "history-unavailable"),
    ("raise", "malformed-pr-authorization", "heavy", None, "malformed-pr"),
    ("raise", "inadmissible-generic-grammar", "heavy", None, "generic-deny"),
)
FORMER_DENIAL_IDS = {
    "parse-uncertain": "PGG-PARSE-UNCERTAIN",
    "missing-transcript": "PRG-TRANSCRIPT-UNAVAILABLE",
    "history-unavailable": "PRG-TRANSCRIPT-UNAVAILABLE",
    "malformed-pr-authorization": "PRG-AUTH-MALFORMED",
    "inadmissible-generic-grammar": "PGG-PUSH-OPTION",
}


def _wrong_declared_value(value):
    if value is None:
        return object()
    if type(value) is bool:
        return 1
    if type(value) is int:
        return True
    if type(value) is str:
        return []
    if type(value) is tuple:
        return list(value)
    return object()


def _schema_mutations(value, seen, path="result"):
    """Yield one root-rebuild mutation for every immutable schema field."""
    if not (isinstance(value, tuple) and hasattr(type(value), "_fields")):
        return
    for field in value._fields:
        child = getattr(value, field)
        key = (type(value), field)
        if key not in seen:
            seen.add(key)
            yield f"{path}.{field}", value._replace(
                **{field: _wrong_declared_value(child)}
            )
        if isinstance(child, tuple) and hasattr(type(child), "_fields"):
            for nested_path, nested in _schema_mutations(
                child, seen, f"{path}.{field}"
            ):
                yield nested_path, value._replace(**{field: nested})
        elif type(child) is tuple:
            element_types = set()
            for index, item in enumerate(child):
                item_type = type(item)
                if item_type in element_types:
                    continue
                element_types.add(item_type)
                if isinstance(item, tuple) and hasattr(item_type, "_fields"):
                    for nested_path, nested in _schema_mutations(
                        item, seen, f"{path}.{field}[{index}]"
                    ):
                        rebuilt = list(child)
                        rebuilt[index] = nested
                        yield nested_path, value._replace(
                            **{field: tuple(rebuilt)}
                        )


def test_a3_gate_target_is_the_single_five_field_test_owner() -> None:
    assert GateTarget._fields == (
        "label",
        "runner_path",
        "policy_path",
        "preflight_path",
        "common_path",
    )
    production = "\n".join(
        target.policy_path.read_text(encoding="utf-8")
        + target.runner_path.read_text(encoding="utf-8")
        for target in TARGETS
    )
    assert "GateTarget" not in production


def test_r4_deep_contract_rejects_all_top_level_and_nested_mutations() -> None:
    """GUARD-A3-PREFLIGHT-DEEP-CONTRACT."""
    target = TARGETS[0]
    module = _load(target.preflight_path, "r4_deep_contract_preflight")
    allow = module.build_preflight({"agent_id": "subagent"})
    assert module.validate_preflight_result(allow) is allow
    parsed_result = module.build_preflight(
        {
            "tool_name": "Bash", "cwd": str(ROOT),
            "tool_input": {"command": "git push origin main"},
        }
    )
    parsed = parsed_result.parsed
    assert parsed is not None
    rich_result = parsed_result._replace(
        outcome="DEFER",
        reason_id="PFP-HEAVY",
        continuation="EVALUATE_HEAVY",
        transcript_path="fixture-transcript.jsonl",
        current_turn_status="found",
        generic_decision=module.classify_generic_push(parsed),
        failure_id=None,
        repository_workdir=str(ROOT.resolve()),
        repository_workdir_source="envelope",
    )
    assert module.validate_preflight_result(rich_result) is rich_result
    seen = set()
    mutations = list(_schema_mutations(rich_result, seen))
    assert {path.split(".", 2)[1] for path, _value in mutations} == set(
        module.PreflightResult._fields
    )
    assert any(path.startswith("result.parsed.") for path, _value in mutations)
    assert any(
        path.startswith("result.generic_decision.")
        for path, _value in mutations
    )
    for path, candidate in mutations:
        try:
            module.validate_preflight_result(candidate)
        except (TypeError, ValueError):
            pass
        else:
            raise AssertionError(f"R4-DEEP-MUTATION-ACCEPTED:{path}")

    foreign = tuple(rich_result)
    for candidate in (foreign, foreign[:-1], foreign + (None,)):
        try:
            module.validate_preflight_result(candidate)
        except TypeError:
            pass
        else:
            raise AssertionError("R4-DEEP-FOREIGN-SHAPE-ACCEPTED")


def _builder_positive_results(module, tmp_path: Path):
    transcript = tmp_path / "preflight-branches.jsonl"
    transcript.write_text(
        json.dumps({
            "type": "user",
            "message": {"role": "user", "content": [{"type": "text", "text": "push"}]},
        }) + "\n",
        encoding="utf-8",
    )
    rows = (
        module.build_preflight({"agent_id": "subagent"}),
        module.build_preflight({"tool_input": "bad"}),
        module.build_preflight({"tool_input": {}}),
        module.build_preflight({"tool_name": "Bash", "tool_input": {"command": "echo safe"}}),
        module.build_preflight({"tool_name": "Bash", "tool_input": {"command": "git push --dry-run origin main"}}),
        module.build_preflight({"tool_name": "Bash", "tool_input": {"command": "env 1=x"}}),
        module.build_preflight({"tool_name": "Bash", "tool_input": {"command": "git push origin main"}}),
        module.build_preflight({
            "tool_name": "Bash",
            "cwd": str(ROOT),
            "tool_input": {"command": "git push origin main"},
            "transcript_path": str(transcript),
        }),
    )
    parsed = module.parse_shell_command("git push origin main", "posix")
    deny_known = module.validate_preflight_result(module.PreflightResult(
        "DEFER", "PFP-DENY-KNOWN", "RENDER_DENY",
        None, None, "", None, None, None, False,
        "PRG-TRANSCRIPT-UNAVAILABLE",
    ))
    deny_internal = module.validate_preflight_result(module.PreflightResult(
        "DEFER", "PFP-DENY-INTERNAL", "RENDER_DENY",
        None, None, "", None, None, None, False, None,
    ))
    malformed = module.build_preflight_from_stdin
    original = module.read_stdin_utf8
    try:
        def fail_read():
            raise ValueError("synthetic malformed stdin")
        module.read_stdin_utf8 = fail_read
        malformed_result = malformed()
    finally:
        module.read_stdin_utf8 = original
    approved_transcript = tmp_path / "approved.jsonl"
    approved_transcript.write_text(
        json.dumps({
            "type": "user",
            "message": {"role": "user", "content": [{"type": "text", "text": "[approve-publication]"}]},
        }) + "\n",
        encoding="utf-8",
    )
    approved = module.build_preflight({
        "tool_name": "Bash",
        "tool_input": {"command": "git push origin main"},
        "transcript_path": str(approved_transcript),
    })
    return (*rows, deny_known, deny_internal, malformed_result, approved)


def test_r5_preflight_reason_branches_are_exhaustive_and_coherent(tmp_path: Path) -> None:
    """GUARD-A3-PREFLIGHT-DEEP-CONTRACT: valid tokens cannot cross branches."""
    module = _load(TARGETS[0].preflight_path, "r5_reason_branch_preflight")
    positives = _builder_positive_results(module, tmp_path)
    by_reason = {result.reason_id: result for result in positives}
    assert set(by_reason) == set(PREFLIGHT_REASON_BRANCHES)
    rich = by_reason["PFP-HEAVY"]
    deny = by_reason["PFP-DENY-TRANSCRIPT"]
    donors = {
        "command": rich.command,
        "dialect": rich.dialect,
        "transcript_path": rich.transcript_path,
        "parsed": rich.parsed,
        "current_turn_status": rich.current_turn_status,
        "generic_decision": rich.generic_decision,
        "failure_id": deny.failure_id,
        "repository_workdir": rich.repository_workdir,
        "repository_workdir_source": rich.repository_workdir_source,
    }
    defaults = {
        "command": None,
        "dialect": None,
        "transcript_path": "",
        "parsed": None,
        "current_turn_status": None,
        "generic_decision": None,
        "failure_id": None,
        "repository_workdir": "",
        "repository_workdir_source": "",
    }
    for reason_id, result in by_reason.items():
        assert module.validate_preflight_result(result) is result
        assert (result.outcome, result.continuation) == PREFLIGHT_REASON_BRANCHES[reason_id]
        for foreign_reason in PREFLIGHT_REASON_BRANCHES:
            if (
                foreign_reason == reason_id
                or PREFLIGHT_REASON_BRANCHES[foreign_reason]
                == PREFLIGHT_REASON_BRANCHES[reason_id]
            ):
                continue
            try:
                module.validate_preflight_result(result._replace(reason_id=foreign_reason))
            except ValueError:
                pass
            else:
                raise AssertionError(
                    f"R5-BRANCH-REASON-ACCEPTED:{reason_id}->{foreign_reason}"
                )
        present = PREFLIGHT_REASON_PRESENT_FIELDS[reason_id]
        for field in donors:
            value = defaults[field] if field in present else donors[field]
            try:
                module.validate_preflight_result(result._replace(**{field: value}))
            except ValueError:
                pass
            else:
                raise AssertionError(
                    f"R5-BRANCH-FIELD-ACCEPTED:{reason_id}:{field}"
                )
        if reason_id not in {"PFP-ALLOW-USER-APPROVED", "PFP-HEAVY"}:
            try:
                module.validate_preflight_result(
                    result._replace(push_instruction=True)
                )
            except ValueError:
                pass
            else:
                raise AssertionError(
                    f"R5-BRANCH-PUSH-INSTRUCTION-ACCEPTED:{reason_id}"
                )


def test_r4_public_interface_is_explicit_minimal_and_used() -> None:
    """GUARD-A3-PUBLIC-INTERFACE."""
    tree = ast.parse(TARGETS[0].policy_path.read_text(encoding="utf-8"))
    imports = [
        node for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "git_push_gate_preflight"
    ]
    assert len(imports) == 1
    imported = tuple(alias.name for alias in imports[0].names)
    expected = (
        "PreflightResult", "validate_preflight_result",
        "build_preflight_from_stdin", "ShellParseResult", "PrRouteDenied",
        "resolve_command_dialect", "parse_transcript_command",
        "project_scan_range_binding",
    )
    assert imported == expected
    assert "*" not in imported
    assert all(not name.startswith("_") for name in imported)
    loaded = {
        node.id for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    assert set(imported) <= loaded


def test_r4_c6_current_state_has_no_cached_import_or_retired_dispatch_residue() -> None:
    """GUARD-A3-C6-CURRENT-STATE."""
    live = (
        TARGETS[0].runner_path,
        TARGETS[0].policy_path,
        TARGETS[0].preflight_path,
        Path(__file__),
        ROOT / "tests" / "test_git_push_gate_hook.py",
        ROOT / "tests" / "git_push_gate_target.py",
    )
    retired = tuple(
        "".join(parts) for parts in (
            ("cached", "-import"),
            ("evaluate", "_push_for_test"),
            ("module.evaluate", "_push ="),
        )
    )
    for path in live:
        text = path.read_text(encoding="utf-8")
        for token in retired:
            assert token not in text, f"R4-C6-RESIDUE:{path.name}:{token}"


def test_r4_gate_target_is_consumed_by_both_complete_layout_suites() -> None:
    """GUARD-A3-GATETARGET-MATRIX."""
    hook_source = (ROOT / "tests" / "test_git_push_gate_hook.py").read_text(
        encoding="utf-8"
    )
    runner_source = Path(__file__).read_text(encoding="utf-8")
    assert "from git_push_gate_target import GateTarget, target_for" in hook_source
    assert "TARGETS = tuple(" in hook_source
    assert "from git_push_gate_target import GateTarget, target_for" in runner_source
    assert tuple(target.label for target in TARGETS) == ("canonical", "codex", "claude")
    hook_tree = ast.parse(hook_source)
    runner_tree = ast.parse(runner_source)
    hook_loaders = {
        node.name: ast.get_source_segment(hook_source, node) or ""
        for node in hook_tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {"run_hook", "_target_for_policy", "_load_gate_module"}
    }
    assert set(hook_loaders) == {"run_hook", "_target_for_policy", "_load_gate_module"}
    assert "_load_gate_module(script" in hook_loaders["run_hook"]
    assert "target.policy_path == script" in hook_loaders["_target_for_policy"]
    assert "target.common_path" in hook_loaders["_load_gate_module"]
    assert "target.preflight_path" in hook_loaders["_load_gate_module"]
    assert "target.policy_path" in hook_loaders["_load_gate_module"]
    local_loaders = {
        node.name: ast.get_source_segment(runner_source, node) or ""
        for node in runner_tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {"_load_gate_target", "_exercise_former_row", "_run"}
    }
    assert set(local_loaders) == {"_load_gate_target", "_exercise_former_row", "_run"}
    for field in GateTarget._fields:
        assert f"target.{field}" in local_loaders["_load_gate_target"] or field == "label"
    assert "target" in local_loaders["_exercise_former_row"]
    assert "target.runner_path" in local_loaders["_run"]
    assert "target.policy_path" in local_loaders["_run"]


def test_r4_no_test_dispatch_or_namespace_forwarder_exists() -> None:
    """GUARD-A3-NO-TEST-DISPATCH."""
    for path in (Path(__file__), ROOT / "tests" / "test_git_push_gate_hook.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        assert not any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in {
                "".join(("evaluate", "_push")),
                "".join(("evaluate", "_push_for_test")),
            }
            for node in ast.walk(tree)
        )
        assert "".join(("_GateTest", "Composite")) not in source
        assert "".join(("module.evaluate", "_push =")) not in source


def test_r4_all_return_paths_inventory_is_hash_bound_and_complete() -> None:
    """GUARD-A3-ALL-RETURN-PATHS."""
    counts = Counter(kind for kind, _row in FORMER_PATH_INVENTORY)
    assert counts == {"return": 9, "raise": 5}
    assert len({row for _kind, row in FORMER_PATH_INVENTORY}) == 14
    baseline = (
        ROOT / ".scratch" / "current-turn-p95-runtime-20260811" / "a3"
        / "baseline" / "scripts" / "universal-hooks" / "scripts"
        / "check-git-push-gate.py"
    )
    if baseline.is_file():
        assert hashlib.sha256(baseline.read_bytes()).hexdigest().upper() == (
            FORMER_EVALUATE_PUSH_SHA256
        )
    executable_counts = Counter(kind for kind, *_rest in FORMER_EXECUTABLE_ROWS)
    assert executable_counts == {"return": 9, "raise": 5}
    assert tuple(row[1] for row in FORMER_EXECUTABLE_ROWS) == tuple(
        row for _kind, row in FORMER_PATH_INVENTORY
    )


def _load_gate_target(target: GateTarget, suffix: str):
    script_dir = str(target.policy_path.parent)
    added = script_dir not in sys.path
    if added:
        sys.path.insert(0, script_dir)
    try:
        sys.modules.pop("hook_common", None)
        sys.modules.pop("git_push_gate_preflight", None)
        common = _load(target.common_path, "hook_common")
        preflight = _load(target.preflight_path, "git_push_gate_preflight")
        policy = _load(target.policy_path, f"r5_policy_{target.label}_{suffix}")
        runner = _load(target.runner_path, f"r5_runner_{target.label}_{suffix}")
        return common, preflight, policy, runner
    finally:
        if added:
            sys.path.remove(script_dir)


def _former_envelope(row_id: str, tmp_path: Path):
    if row_id == "approval-allow":
        text, command = "[approve-publication]", "git push origin main"
    elif row_id == "active-pr-result":
        text, command = "continue", "git push origin main"
    elif row_id == "generic-scan-allow":
        text, command = "push now", "git push origin main"
    elif row_id == "no-allow-deny":
        text, command = "continue", "git push origin main"
    elif row_id == "history-unavailable":
        text, command = "continue", "git push origin main"
    elif row_id == "malformed-pr-authorization":
        text, command = "continue", "git push origin main"
    elif row_id == "inadmissible-generic-grammar":
        text, command = "push now", "git push --unknown origin main"
    else:
        raise AssertionError(f"unknown deferred row: {row_id}")
    transcript = tmp_path / f"{row_id}.jsonl"
    transcript.write_text(
        json.dumps({
            "type": "user",
            "message": {"role": "user", "content": [{"type": "text", "text": text}]},
        }) + "\n",
        encoding="utf-8",
    )
    return {
        "tool_name": "Bash",
        "cwd": str(ROOT),
        "tool_input": {"command": command},
        "transcript_path": str(transcript),
    }


def _exercise_former_row(target: GateTarget, row, tmp_path: Path, root: str):
    kind, row_id, owner, static_envelope, scenario = row
    _common, preflight, policy, runner = _load_gate_target(
        target, f"{root}_{row_id.replace('-', '_')}"
    )
    envelope = static_envelope or _former_envelope(row_id, tmp_path)
    counters = Counter()
    original_read = preflight.read_stdin_utf8
    original_parse = preflight.parse_shell_command
    original_build = preflight.build_preflight_from_stdin
    original_heavy = policy.evaluate_heavy

    def counted_read():
        counters["stdin"] += 1
        return json.dumps(envelope)

    def counted_parse(*args, **kwargs):
        counters["parse"] += 1
        return original_parse(*args, **kwargs)

    def counted_build():
        counters["preflight"] += 1
        return original_build()

    def counted_heavy(value):
        counters["heavy"] += 1
        return original_heavy(value)

    patches = [
        mock.patch.object(preflight, "read_stdin_utf8", side_effect=counted_read),
        mock.patch.object(preflight, "parse_shell_command", side_effect=counted_parse),
        mock.patch.object(preflight, "build_preflight_from_stdin", side_effect=counted_build),
        mock.patch.object(policy, "build_preflight_from_stdin", side_effect=counted_build),
        mock.patch.object(policy, "evaluate_heavy", side_effect=counted_heavy),
    ]
    if scenario in {"active-pr", "generic-scan", "plain-deny", "malformed-pr"}:
        patches.append(mock.patch.object(
            policy, "read_transcript_history", return_value=([{"type": "user"}], "found")
        ))
    if scenario == "active-pr":
        grant = object()
        patches.extend((
            mock.patch.object(policy, "_derive_pr_grant", return_value=("active", grant)),
            mock.patch.object(policy, "_evaluate_active_pr_route", side_effect=lambda *_args: counters.update({"owner": 1}) or True),
        ))
    elif scenario == "generic-scan":
        patches.extend((
            mock.patch.object(policy, "_derive_pr_grant", return_value=("none", None)),
            mock.patch.object(policy, "_resolve_generic_scan_binding", return_value=object()),
            mock.patch.object(policy, "_run_authoritative_scan", side_effect=lambda *_args: counters.update({"owner": 1})),
        ))
    elif scenario == "plain-deny":
        patches.append(mock.patch.object(policy, "_derive_pr_grant", return_value=("none", None)))
    elif scenario == "history-unavailable":
        patches.append(mock.patch.object(policy, "read_transcript_history", return_value=([], "unreadable")))
    elif scenario == "malformed-pr":
        patches.append(mock.patch.object(policy, "_derive_pr_grant", return_value=("malformed", None)))
    elif scenario == "generic-deny":
        patches.extend((
            mock.patch.object(policy, "read_transcript_history", return_value=([{"type": "user"}], "found")),
            mock.patch.object(policy, "_derive_pr_grant", return_value=("none", None)),
        ))

    stdout, stderr = io.StringIO(), io.StringIO()
    for patcher in patches:
        patcher.start()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            if root == "direct":
                result = policy.main()
            else:
                def load_policy(_runner):
                    counters["policy_load"] += 1
                    return policy
                with mock.patch.object(runner, "_load_preflight", return_value=(target.runner_path, preflight)), \
                     mock.patch.object(runner, "_load_policy", side_effect=load_policy):
                    result = runner.main()
    finally:
        for patcher in reversed(patches):
            patcher.stop()
    assert counters["preflight"] == 1
    assert counters["stdin"] == 1
    expected_parse = 0 if row_id in {
        "subagent-allow", "non-dict-allow", "missing-command-allow"
    } else 1
    assert counters["parse"] == expected_parse
    expected_heavy = 1 if owner == "heavy" else 0
    assert counters["heavy"] == expected_heavy
    if scenario in {"active-pr", "generic-scan"}:
        assert counters["owner"] == 1
    expected_policy_load = 0 if kind == "return" and owner == "preflight" else 1
    if root == "runner":
        assert counters["policy_load"] == expected_policy_load
    return result, stdout.getvalue(), stderr.getvalue(), counters


def test_r5_all_former_paths_execute_through_real_target_owners(tmp_path: Path) -> None:
    """GUARD-A3-ALL-RETURN-PATHS: executable 9-return/5-raise matrix."""
    for target in TARGETS:
        for row in FORMER_EXECUTABLE_ROWS:
            direct = _exercise_former_row(target, row, tmp_path, "direct")
            runner = _exercise_former_row(target, row, tmp_path, "runner")
            assert runner[:3] == direct[:3], (target.label, row[1], direct, runner)
            result, stdout, stderr, _counters = runner
            assert type(result) is int and result == 0
            assert stderr == ""
            if row[0] == "return" and row[1] != "no-allow-deny":
                assert stdout == ""
            else:
                payload = json.loads(stdout)
                specific = payload["hookSpecificOutput"]
                assert specific["permissionDecision"] == "deny"
                if row[0] == "raise":
                    assert specific["permissionDecisionReason"].startswith(
                        FORMER_DENIAL_IDS[row[1]] + ":"
                    )


def test_r4_result_composition_has_one_owner_and_both_main_paths_use_it() -> None:
    """GUARD-A3-RESULT-COMPOSITION."""
    tree = ast.parse(TARGETS[0].policy_path.read_text(encoding="utf-8"))
    composers = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "compose_gate_result"
    ]
    assert len(composers) == 1
    main = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    calls = [
        node for node in ast.walk(main)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "compose_gate_result"
    ]
    assert len(calls) == 1


def test_r4_termination_roots_are_exactly_two_and_reusable_code_never_terminates() -> None:
    """GUARD-A3-TERMINATION-ROOTS."""
    roots = 0
    for path in (TARGETS[0].policy_path, TARGETS[0].runner_path):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.If) and any(
                isinstance(part, ast.Compare)
                and any(isinstance(value, ast.Constant) and value.value == "__main__"
                        for value in ast.walk(part))
                for part in ast.walk(node.test)
            ):
                roots += 1
        for function in (
            node for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ):
            for call in (node for node in ast.walk(function) if isinstance(node, ast.Call)):
                name = (
                    call.func.id if isinstance(call.func, ast.Name)
                    else call.func.attr if isinstance(call.func, ast.Attribute)
                    else ""
                )
                assert name not in {"exit", "_exit", "abort"}
    assert roots == 2


def test_a3_preflight_contract_and_old_owner_are_red_until_relocated() -> None:
    expected = (
        "outcome",
        "reason_id",
        "continuation",
        "command",
        "dialect",
        "transcript_path",
        "parsed",
        "current_turn_status",
        "generic_decision",
        "push_instruction",
        "failure_id",
        "repository_workdir",
        "repository_workdir_source",
    )
    for target in TARGETS:
        assert target.preflight_path.is_file(), f"A3-PREFLIGHT-MISSING:{target.label}"
        module = _load(target.preflight_path, f"a3_preflight_{target.label}")
        assert module.PreflightResult._fields == expected
        policy_tree = ast.parse(target.policy_path.read_text(encoding="utf-8"))
        assert not any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "evaluate_push"
            for node in ast.walk(policy_tree)
        ), f"A3-OWNER-DUPLICATION:{target.label}"


def _load(path: Path, name: str):
    script_dir = str(path.parent)
    added = script_dir not in sys.path
    if added:
        sys.path.insert(0, script_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        return module
    finally:
        if added:
            sys.path.remove(script_dir)


def _run(
    target: GateTarget,
    envelope: dict,
    *,
    surface: str = "runner",
    env: dict[str, str] | None = None,
):
    script = target.runner_path if surface == "runner" else target.policy_path
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(envelope),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env=env,
        check=False,
        timeout=20,
    )


def _copy_runner(target_dir: Path) -> GateTarget:
    target = target_for("temporary", target_dir)
    shutil.copy2(CANON_DIR / RUNNER_NAME, target.runner_path)
    target.common_path.write_text("# fixed synthetic sibling\n", encoding="utf-8")
    target.preflight_path.write_text(
        "from typing import NamedTuple\n"
        "class Result(NamedTuple): outcome: str\n"
        "def build_preflight_from_stdin(): return Result('DEFER')\n"
        "def validate_preflight_result(value): return value\n",
        encoding="utf-8",
    )
    return target


def _assert_runner_deny(completed: subprocess.CompletedProcess[str]) -> None:
    assert completed.returncode == 0
    assert completed.stderr == ""
    payload = json.loads(completed.stdout)
    specific = payload["hookSpecificOutput"]
    assert specific["hookEventName"] == "PreToolUse"
    assert specific["permissionDecision"] == "deny"
    reason = specific["permissionDecisionReason"]
    assert reason.startswith(EXPECTED_FAILURE_ID + ":")
    for forbidden in (
        "Traceback",
        str(ROOT),
        "git push",
        "RuntimeError",
        "SENSITIVE-PREFAILURE-OUTPUT",
    ):
        assert forbidden not in completed.stdout


def test_runner_is_mirrored_and_installer_registers_it() -> None:
    runner_bytes = [(directory / RUNNER_NAME).read_bytes() for directory in SCRIPT_DIRS]
    assert runner_bytes[0] == runner_bytes[1] == runner_bytes[2]

    installer = _load(ROOT / "scripts" / "production_installer.py", "runner_installer")
    for provider, installed_root in (
        ("codex", Path("/installed/codex/lead")),
        ("claude", Path("/installed/claude/agents")),
    ):
        specs = installer._hook_specs(provider, installed_root)
        matches = [row for row in specs if row[0] == "check-git-push-gate"]
        assert len(matches) == 1
        assert matches[0][1].name == RUNNER_NAME


def test_runner_and_direct_policy_are_semantically_equivalent(tmp_path: Path) -> None:
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        json.dumps(
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "[approve-publication]"}],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    envelopes = (
        {
            "tool_name": "Bash",
            "tool_input": {"command": "echo safe"},
            "transcript_path": str(transcript),
        },
        {
            "tool_name": "Bash",
            "tool_input": {"command": "git push origin main"},
            "transcript_path": str(transcript),
        },
        {
            "tool_name": "Bash",
            "tool_input": {"command": "git push origin main"},
            "transcript_path": str(tmp_path / "missing.jsonl"),
        },
    )
    for target in TARGETS:
        for envelope in envelopes:
            direct = _run(target, envelope, surface="policy")
            delegated = _run(target, envelope)
            assert (
                delegated.returncode,
                delegated.stdout,
                delegated.stderr,
            ) == (direct.returncode, direct.stdout, direct.stderr)


def test_runner_uses_only_fixed_sibling_and_cache_is_optional(tmp_path: Path) -> None:
    runner = _copy_runner(tmp_path)
    (tmp_path / POLICY_NAME).write_text(
        "def main(_preflight=None):\n    print('SIBLING')\n    return 0\n",
        encoding="utf-8",
    )
    lookalike = tmp_path / "lookalike"
    lookalike.mkdir()
    (lookalike / POLICY_NAME).write_text(
        "raise RuntimeError('LOOKALIKE EXECUTED')\n", encoding="utf-8"
    )
    envelope = {"tool_name": "Bash", "tool_input": {"command": "git push"}}
    base_env = os.environ.copy()
    base_env["PYTHONPATH"] = str(lookalike)

    ordinary = _run(runner, envelope, env=base_env)
    no_cache_env = dict(base_env)
    no_cache_env["PYTHONDONTWRITEBYTECODE"] = "1"
    no_cache = _run(runner, envelope, env=no_cache_env)

    assert (ordinary.returncode, ordinary.stdout, ordinary.stderr) == (0, "SIBLING\n", "")
    assert (no_cache.returncode, no_cache.stdout, no_cache.stderr) == (0, "SIBLING\n", "")


def test_runner_rejects_ambient_bytecode_cache_prefix(tmp_path: Path) -> None:
    runner = _copy_runner(tmp_path)
    (tmp_path / POLICY_NAME).write_text(
        "import sys\ndef main(_preflight=None):\n    print(repr(sys.pycache_prefix))\n    return 0\n",
        encoding="utf-8",
    )
    ambient_cache = tmp_path / "ambient-cache"
    ambient_cache.mkdir()
    environment = os.environ.copy()
    environment["PYTHONPYCACHEPREFIX"] = str(ambient_cache)
    completed = _run(
        runner,
        {"tool_name": "Bash", "tool_input": {"command": "git push"}},
        env=environment,
    )
    assert (completed.returncode, completed.stdout, completed.stderr) == (0, "None\n", "")


def test_runner_terminal_preflight_never_loads_heavy_policy(tmp_path: Path) -> None:
    runner = _copy_runner(tmp_path)
    (tmp_path / "git_push_gate_preflight.py").write_text(
        "from typing import NamedTuple\n"
        "class Result(NamedTuple): outcome: str\n"
        "def build_preflight_from_stdin(): return Result('ALLOW_FINAL')\n"
        "def validate_preflight_result(value): return value\n",
        encoding="utf-8",
    )
    (tmp_path / POLICY_NAME).write_text(
        "raise RuntimeError('HEAVY-POLICY-LOADED')\n", encoding="utf-8"
    )
    completed = _run(
        runner, {"tool_name": "Bash", "tool_input": {"command": "echo safe"}}
    )
    assert (completed.returncode, completed.stdout, completed.stderr) == (0, "", "")


def test_runner_preflight_failures_are_buffered_and_fail_closed(tmp_path: Path) -> None:
    runner = _copy_runner(tmp_path)
    preflight = tmp_path / "git_push_gate_preflight.py"
    cases = (
        "raise RuntimeError('PRELOAD')\n",
        "print('SENSITIVE-PREFAILURE-OUTPUT')\nraise KeyboardInterrupt()\n",
        "def build_preflight_from_stdin(): return object()\n"
        "def validate_preflight_result(_value): raise TypeError('foreign')\n",
    )
    for source in cases:
        preflight.write_text(source, encoding="utf-8")
        _assert_runner_deny(
            _run(runner, {"tool_name": "Bash", "tool_input": {"command": "git push"}})
        )


def test_runner_denies_instead_of_importing_ambient_hook_common(tmp_path: Path) -> None:
    runner = _copy_runner(tmp_path)
    fixed_common = tmp_path / "hook_common.py"
    fixed_common.unlink()
    (tmp_path / POLICY_NAME).write_text(
        "import hook_common\ndef main():\n    print(hook_common.SOURCE)\n    return 0\n",
        encoding="utf-8",
    )
    lookalike = tmp_path / "lookalike"
    lookalike.mkdir()
    (lookalike / "hook_common.py").write_text(
        "SOURCE = 'AMBIENT-HOOK-COMMON'\n", encoding="utf-8"
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(lookalike)
    completed = _run(
        runner,
        {"tool_name": "Bash", "tool_input": {"command": "git push"}},
        env=environment,
    )
    _assert_runner_deny(completed)
    assert "AMBIENT-HOOK-COMMON" not in completed.stdout


def test_runner_fails_closed_for_all_predelegation_failures(tmp_path: Path) -> None:
    runner = _copy_runner(tmp_path)
    policy = tmp_path / POLICY_NAME
    envelope = {"tool_name": "Bash", "tool_input": {"command": "git push"}}

    cases: tuple[tuple[str, str | None], ...] = (
        ("missing", None),
        ("syntax", "def broken(:\n"),
        ("exception", "def main():\n    raise RuntimeError('raw')\n"),
        (
            "output-then-exception",
            "def main():\n    print('SENSITIVE-PREFAILURE-OUTPUT')\n    raise RuntimeError('raw')\n",
        ),
        ("interrupt", "def main():\n    raise KeyboardInterrupt()\n"),
        ("system-exit", "def main():\n    raise SystemExit(7)\n"),
        ("bad-result", "def main():\n    return 'allow'\n"),
    )
    for name, source in cases:
        if policy.exists():
            if policy.is_dir():
                policy.rmdir()
            else:
                policy.unlink()
        if source is not None:
            policy.write_text(source, encoding="utf-8")
        completed = _run(runner, envelope)
        _assert_runner_deny(completed)

    if policy.exists():
        policy.unlink()
    policy.mkdir()
    _assert_runner_deny(_run(runner, envelope))
