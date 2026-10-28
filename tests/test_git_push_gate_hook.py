"""Technical push qualification, fresh scanner and regression tests.

Human review and publication consent belong to Root. These tests exercise only
actual-command qualification, target currentness, scanner results and resources.
"""

from __future__ import annotations

import ast
import contextlib
import dataclasses
import hashlib
import importlib.util
import io
import inspect
import json
import os
import re
import secrets
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import pytest
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from typing import NamedTuple
from unittest import mock
from urllib.parse import quote

from git_push_gate_target import GateTarget, target_for


class TestTechnicalPublication:
    @contextlib.contextmanager
    def repository(self):
        with tempfile.TemporaryDirectory(prefix="publication-technical-") as directory:
            root = Path(directory) / "repo"
            remote = Path(directory) / "remote.git"
            subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True, timeout=30)
            subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True, timeout=30)
            subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=root, check=True, timeout=30)
            commits = []
            for text in ("reviewed change\n", "later local change\n"):
                (root / "example.txt").write_text(text, encoding="utf-8")
                subprocess.run(["git", "add", "example.txt"], cwd=root, check=True, timeout=30)
                subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "Synthetic change"], cwd=root, check=True, timeout=30)
                commits.append(subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True, timeout=30).strip())
            yield root, remote, commits

    def preflight(self, module, root, source, **extra):
        command = shlex.join(("git", *module.native_git_config_arguments(),
                              "push", "origin", source + ":refs/heads/main"))
        return module._a3_preflight.build_preflight({
            "tool_name": "Bash", "cwd": str(root),
            "tool_input": {"command": command},
            **extra,
        })

    @contextlib.contextmanager
    def callback(self, module, root, remote, source):
        oid = subprocess.check_output(["git", "rev-parse", source], cwd=root, timeout=30).strip()
        wire = os.fsencode(source) + b" " + oid + b" refs/heads/main " + b"0" * 40 + b"\n"
        previous = Path.cwd()
        output, errors = io.StringIO(), io.StringIO()
        try:
            os.chdir(root)
            with mock.patch.object(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(wire))), \
                 contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                yield lambda: module._native_pre_push_main(["origin", str(remote)]), output, errors
        finally:
            os.chdir(previous)

    def test_real_scanner_uses_selected_source_without_reading_history(self):
        module = _load_gate_module(CANONICAL_HOOK, "technical_actual_range")
        common = sys.modules["hook_common"]
        with self.repository() as (root, remote, commits):
            before = {path: path.read_bytes() for path in root.glob("*") if path.is_file()}
            with mock.patch.object(common, "read_transcript_history", side_effect=AssertionError("history read")), mock.patch.object(common, "scan_current_turn_boundary", side_effect=AssertionError("turn read")), mock.patch.object(common, "hold_native_history_source", side_effect=AssertionError("history acquisition")), mock.patch.object(module, "_run_authoritative_scan", wraps=module._run_authoritative_scan) as scan:
                for extra in ({}, {"transcript_path": str(root / "not-a-transcript")}, {"transcript_path": {"invalid": "irrelevant"}}):
                    result = self.preflight(module, root, commits[0], **extra)
                    assert result.continuation == "EVALUATE_HEAVY"
                    assert module.evaluate_heavy(result)
                    with self.callback(module, root, remote, commits[0]) as (invoke, _out, err):
                        assert invoke() == 0, err.getvalue()
                assert scan.call_count == 6
                for call in scan.call_args_list[::2]:
                    binding = call.args[0]
                    assert binding.source_oid == commits[0]
                    assert binding.head_oid == commits[1]
                    assert binding.destination == "refs/heads/main"
            envelope = {
                "tool_name": "exec_command", "cwd": str(root),
                "tool_input": {"cmd": self.preflight(module, root, commits[0]).command, "workdir": str(root)},
            }
            public = subprocess.run(
                [sys.executable, "-B", str(CANONICAL_HOOK.with_name("check-git-push-gate-runner.py"))],
                input=json.dumps(envelope), capture_output=True, text=True, timeout=60,
            )
            assert (public.returncode, public.stdout, public.stderr) == (0, "", "")
            assert {path: path.read_bytes() for path in root.glob("*") if path.is_file()} == before
            assert not (remote / "refs" / "heads" / "main").exists()

    @pytest.mark.parametrize("changed", ("head", "source", "endpoint", "repository"))
    def test_target_drift_after_scan_refuses(self, changed):
        module = _load_gate_module(CANONICAL_HOOK, "technical_drift_" + changed)
        with self.repository() as (root, remote, commits):
            source = "main" if changed == "source" else commits[0]
            scan = module._run_authoritative_scan
            currentness = module._native_callback_currentness
            def drift(*args, **kwargs):
                evidence = scan(*args, **kwargs)
                if changed == "endpoint":
                    subprocess.run(["git", "remote", "set-url", "--push", "origin", str(remote) + ".changed"], cwd=root, check=True, timeout=30)
                elif changed in {"head", "source"}:
                    subprocess.run(["git", "update-ref", "refs/heads/main", commits[0]], cwd=root, check=True, timeout=30)
                else:
                    # Repository replacement is observed by the native owner.
                    module._native_callback_currentness = lambda *a: currentness(*a) + (b"changed repository",)
                return evidence
            with self.callback(module, root, remote, source) as (invoke, out, err), \
                 mock.patch.object(module, "_run_authoritative_scan", side_effect=drift) as observed:
                assert invoke() == 2
                assert "PGG-TARGET-CURRENTNESS" in err.getvalue()
                assert out.getvalue() == ""
                observed.assert_called_once()

    @pytest.mark.parametrize("failure", ("PGG-SCAN-FINDING", "PGG-SCAN-REFUSAL", "PGG-SCAN-EXECUTION", "PGG-SCAN-CORRELATION"))
    def test_scan_failure_is_not_converted_to_allow(self, failure):
        module = _load_gate_module(CANONICAL_HOOK, "technical_scan_failure")
        with self.repository() as (root, remote, commits):
            result = self.preflight(module, root, commits[0])
            assert module.evaluate_heavy(result)
            with self.callback(module, root, remote, commits[0]) as (invoke, out, err), \
                 mock.patch.object(module, "_run_authoritative_scan", side_effect=module.PrRouteDenied(failure)):
                assert invoke() == 2
            assert out.getvalue() == ""
            assert failure in err.getvalue()

    def test_multiple_effects_and_missing_destination_refuse_before_scan(self):
        module = _load_gate_module(CANONICAL_HOOK, "technical_shape")
        for command in ("git push origin HEAD:refs/heads/main HEAD:refs/heads/other", "git push origin", "git push origin HEAD:refs/heads/main; git push origin HEAD:refs/heads/other"):
            result = module._a3_preflight.build_preflight({"tool_name": "Bash", "cwd": str(REPO_ROOT), "tool_input": {"command": command}})
            with mock.patch.object(module, "_run_authoritative_scan") as scan:
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    module.compose_gate_result(result)
                assert json.loads(out.getvalue())["hookSpecificOutput"]["permissionDecision"] == "deny"
                scan.assert_not_called()

REPO_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_HOOK = REPO_ROOT / "scripts" / "universal-hooks" / "scripts" / "check-git-push-gate.py"
HOOKS = (
    REPO_ROOT / "src.claude" / "agents" / "scripts" / "check-git-push-gate.py",
    REPO_ROOT / "src.codex" / "skills" / "lead" / "scripts" / "check-git-push-gate.py",
)
TARGETS = tuple(
    target_for(label, directory)
    for label, directory in (
        ("canonical", CANONICAL_HOOK.parent),
        ("codex", HOOKS[1].parent),
        ("claude", HOOKS[0].parent),
    )
)


@contextlib.contextmanager
def pr_literal_command_workspace():
    scratch_parent = REPO_ROOT / ".scratch"
    scratch_parent.mkdir(parents=True, exist_ok=True)
    owned_path: Path | None = None
    try:
        with tempfile.TemporaryDirectory(
            prefix="pr-push-literal-command-", dir=scratch_parent
        ) as temp_dir:
            owned_path = Path(temp_dir)
            yield owned_path
    finally:
        if owned_path is not None:
            assert not owned_path.exists()


@contextlib.contextmanager
def temporary_repository_workdir():
    with tempfile.TemporaryDirectory(prefix="push-gate-process-bounds-") as directory:
        root = Path(directory).resolve()
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        yield str(root)


def user(text: str) -> dict:
    return {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": text}]}}


@contextlib.contextmanager
def synthetic_transcript(entries: list[dict]):
    scratch_parent = REPO_ROOT / ".scratch"
    scratch_parent.mkdir(parents=True, exist_ok=True)
    transcript_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            suffix=".jsonl",
            delete=False,
            dir=scratch_parent,
            encoding="utf-8",
        ) as transcript_file:
            transcript_path = Path(transcript_file.name)
            for entry in entries:
                transcript_file.write(json.dumps(entry, ensure_ascii=False) + "\n")
        yield transcript_path
    finally:
        if transcript_path is not None:
            for suffix in (".pr-publication-binding-v1.json", ".generic-publication-index-v1.json"):
                Path(str(transcript_path) + suffix).unlink(missing_ok=True)
                for temporary in transcript_path.parent.glob(transcript_path.name + suffix + ".tmp-*"):
                    temporary.unlink(missing_ok=True)
            transcript_path.unlink(missing_ok=True)


def _target_for_policy(script: Path) -> GateTarget:
    matches = tuple(target for target in TARGETS if target.policy_path == script)
    assert len(matches) == 1, f"unknown complete gate layout: {script}"
    return matches[0]


def _load_exact_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_gate_module(script: Path | GateTarget, mod_name: str):
    """Import a HOOKS entry directly (not via subprocess) so a test can
    monkeypatch one of its module-level functions to raise -- used only by
    TestCrashWhileDecidingFallsThroughToDeny below, which needs to inject a
    fault INSIDE the running decision code, something a subprocess-driven
    test cannot do. Same sys.path-insert-then-restore pattern as
    tests/test_workitem_sentinels.py's `_load_adapter_module` and
    tests/test_hook_common.py's `_load_hook_common` (the script's own
    directory must be on sys.path for its bare `import hook_common` to
    resolve, since importlib.util.spec_from_file_location does not add it
    automatically the way running the script directly would)."""
    target = script if isinstance(script, GateTarget) else _target_for_policy(script)
    script_dir = str(target.policy_path.parent)
    added = script_dir not in sys.path
    if added:
        sys.path.insert(0, script_dir)
    try:
        # Load the real complete target in the same dependency order as the
        # registered runner. Tests patch the owning module directly.
        sys.modules.pop("hook_common", None)
        sys.modules.pop("git_push_gate_preflight", None)
        _load_exact_module(target.common_path, "hook_common")
        preflight = _load_exact_module(
            target.preflight_path, "git_push_gate_preflight"
        )
        module = _load_exact_module(target.policy_path, mod_name)
        module._a3_preflight = preflight
        return module
    finally:
        if added:
            sys.path.remove(script_dir)


def _heavy_preflight(
    module,
    *,
    command: str = "git push origin main",
    dialect: str = "posix",
    transcript_path: str = "fixture-transcript.jsonl",
    repository_workdir: str | None = None,
    repository_workdir_source: str = "tool",
):
    owner = module._a3_preflight
    parsed = owner.parse_shell_command(command, dialect)
    selected_workdir = (
        str(REPO_ROOT.resolve())
        if repository_workdir is None else repository_workdir
    )
    return owner.validate_preflight_result(owner.PreflightResult(
        "DEFER", "PFP-HEAVY", "EVALUATE_HEAVY", command=command, dialect=dialect,
        parsed=parsed, generic_decision=owner.classify_generic_push(parsed),
        repository_workdir=selected_workdir,
        repository_workdir_source=repository_workdir_source,
    ))


# The scanner's own self-reported RESULT text (check-publication-safety.sh,
# 2026-07-26 hardening) -- these are what check-git-push-gate.py's
# SCAN_CLEAN_TRACKED_REGEX actually matches against tool OUTPUT, never a call.
# Each carries the SAME tool_id/call_id as the invocation it is the real
# answer to (see SCAN_CALL / SCAN_CALL_PATH_MODE / CODEX_SCAN_CALL above) --
# that shared id is the correlation the 2026-07-26 adversarial-gate finding
# proved was missing when these were two independently-matched haystacks.

# THE EXACT REPRODUCTION from work-items/bugs/2026-07-26-push-gate-credits-a-
# blocking-scan-whose-grep-echoes-the-clean-line.md: a real scan invocation's
# own combined output when it BLOCKS on a runtime-assembled credential fixture
# whose `git grep` report line happens to embed the exact
# clean-receipt text as a substring, plus the scanner's own failure-marker
# line. See TestGitPushGate's WHOLE-LINE-vs-SUBSTRING section below for the
# tests that isolate each of the regex's two hardening conditions.
# The key and digit-bearing value stay split into individually harmless source
# fragments so the tracked test remains publication-safe while the assembled
# scanner input retains the real blocking shape.


# --- "different source" fixtures: an UNRELATED tool call/result pair, with
# its OWN distinct id, whose result happens to quote the scanner's exact
# clean-result text. `tests/test_git_push_gate_hook.py` (this very file)
# literally contains that string a few lines above, which is precisely why an
# innocent `Read` of it is a realistic, not contrived, bypass attempt for an
# uncorrelated gate -- and exactly the shape the adversarial gate reproduced
# live against the shipped (pre-correlation) hook.


# --- `--range` mode fixtures. Durable provenance:
# work-items/archive/2026-07/2026-07-26-push-gate-range-receipt/closure.md.
# The scanner's second mode covers the commit set about to be published
# (`<tip> --not --remotes=<remote>`), not the staged index. The gate first
# admits one solitary direct push, then requires the receipt's `remote`/`dst`
# to equal that single grammar binding.
def repository_head_oid() -> str:
    marker = REPO_ROOT / ".git"
    if marker.is_dir():
        git_dir = marker
    else:
        declaration = marker.read_text(encoding="utf-8").strip()
        if not declaration.startswith("gitdir: "):
            raise AssertionError("test repository has no readable Git directory")
        git_dir = (REPO_ROOT / declaration[8:]).resolve()
    head = (git_dir / "HEAD").read_text(encoding="ascii").strip()
    if re.fullmatch(r"[0-9a-fA-F]{40,64}", head):
        return head.lower()
    if not head.startswith("ref: "):
        raise AssertionError("test repository HEAD has an unsupported shape")
    ref_name = head[5:]
    common_dir = git_dir
    common_marker = git_dir / "commondir"
    if common_marker.is_file():
        common_dir = (git_dir / common_marker.read_text(encoding="utf-8").strip()).resolve()
    for root in (git_dir, common_dir):
        loose = root / ref_name
        if loose.is_file():
            return loose.read_text(encoding="ascii").strip().lower()
        packed = root / "packed-refs"
        if packed.is_file():
            suffix = f" {ref_name}"
            for row in packed.read_text(encoding="ascii").splitlines():
                if row.endswith(suffix):
                    return row.split(" ", 1)[0].lower()
    raise AssertionError("test repository HEAD ref is unresolved")


RANGE_TIP = repository_head_oid()


def range_receipt_v3(
    *,
    files: int = 2,
    commits: int = 1,
    remote: str = "origin",
    dst: str = "claude",
    src: str | None = None,
    tip: str = RANGE_TIP,
    digest: str = "a" * 64,
) -> str:
    if commits == 0:
        raise ValueError("V3 receipts require a non-empty commit set")
    objects = commits + files + 1
    return (
        "publication-safety: clean (range, receipt=v3, "
        f"commits={commits}, commit-set={digest}, messages=complete, "
        f"objects={objects}, object-set={'b' * 64}, blobs={files}, "
        f"blob-set={'c' * 64}, blob-bytes={files}, text={files}, binary=0, "
        f"subjects={files}, subject-set={'d' * 64}, paths={files}, "
        f"path-set={'e' * 64}, history=complete, "
        f"remote={quote(remote, safe='-._~')}, dst={quote(dst, safe='-._~')}, "
        f"src={quote(src or tip, safe='-._~')}, tip={tip})"
    )


def test_native_entry_denial_reports_only_fixed_decision_stage(tmp_path: Path, monkeypatch, capsys) -> None:
    """Synthetic PreToolUse coverage; no push or user Git configuration is used."""
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", os.devnull)
    repo = tmp_path / "repo"
    repo.mkdir()
    git = shutil.which("git")
    assert git is not None
    subprocess.run([git, "init", "-q", str(repo)], check=True, timeout=15)
    gate = _load_gate_module(CANONICAL_HOOK, "native_entry_stage_test")
    preflight = gate._a3_preflight
    base = list(gate.native_git_config_arguments())
    sentinel = "SYNTHETIC-NATIVE-PRIVATE"

    def build(options):
        argv = ("git", "-C", str(repo), *options, "push", "origin", "a" * 40 + ":refs/heads/main")
        command = "& " + " ".join("'" + word.replace("'", "''") + "'" for word in argv)
        return preflight.build_preflight({"tool_name": "PowerShell", "cwd": str(repo),
                                          "tool_input": {"command": command, "workdir": str(repo)}})

    def denied(options, stage):
        assert gate.compose_gate_result(build(options)) == 0
        output = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
        assert output["permissionDecision"] == "deny"
        reason = output["permissionDecisionReason"]
        assert reason.startswith("PGG-NATIVE-ENTRY-REQUIRED:")
        assert f"Native-entry diagnostic: stage={stage}." in reason
        assert sentinel not in reason and str(repo) not in reason

    denied([], "invocation-unqualified")
    interpreter = gate._interpreter_identity().absolute_resolved_path
    entry = os.path.abspath(gate.__file__)
    for executable, script in ((str(repo / sentinel / "python.exe"), entry),
                               (interpreter, str(repo / sentinel / "gate.py"))):
        wrong = base.copy()
        wrong[1] = "hook.orchestrarium-publication.command=" + shlex.join((executable, script, "--git-pre-push"))
        denied(wrong, "command-mismatch")
    wrong_event = base.copy()
    wrong_event[5] = "hook.orchestrarium-publication.event=unexpected"
    denied(wrong_event, "registration-event-mismatch")
    both = wrong_event.copy()
    both[1] = "hook.orchestrarium-publication.command=" + sentinel
    denied(both, "command-mismatch")
    assert gate._qualify_native_push_command(build(base)) is True


class TestCanonicalPublicationCommandGrammar(unittest.TestCase):
    ALL_HOOKS = (CANONICAL_HOOK, *HOOKS)

    def _modules(self, suffix: str):
        for index, script in enumerate(self.ALL_HOOKS):
            yield script, _load_gate_module(script, f"publication_grammar_{suffix}_{index}")


    @unittest.skipUnless(os.name == "nt", "Windows host recovery contract")
    def test_wrong_supported_label_uses_the_same_literal_dispatch_proof(self) -> None:
        git = str(Path(shutil.which("git")).resolve(strict=True))
        raw = "& '" + git + "' push origin 'HEAD:refs/heads/main'"
        for script, module in self._modules("wrong_supported_label"):
            owner = module._a3_preflight
            for name, field in (("Bash", "command"), ("PowerShell", "command"), ("functions.exec_command", "cmd")):
                with self.subTest(script=script, operation=name):
                    pre = owner.build_preflight({"tool_name": name, "tool_input": {field: raw}, "cwd": str(REPO_ROOT)})
                    self.assertEqual(pre.dialect, "powershell")
                    self.assertEqual(owner.classify_generic_push(pre.parsed).status, "PGG-ADMISSIBLE")
                    self.assertIs(owner.literal_direct_command(pre.parsed), pre.parsed.effective_publications.records[0].push.command)
                    self.assertEqual(pre.parsed.raw_command, raw)
                    self.assertIsNone(pre.failure_id)
                    self.assertEqual(pre.continuation, "EVALUATE_HEAVY")

    def test_wrong_label_recovery_preserves_host_primary_and_correlation_guards(self) -> None:
        module = _load_gate_module(CANONICAL_HOOK, "recovery_guard_pairs")
        owner = module._a3_preflight
        raw = "& 'literal-git' push origin 'HEAD:refs/heads/main'"
        resolution = owner.CommandDialectResolution("posix", True)
        primary = owner.parse_shell_command(raw, "posix")
        for host in ("posix", "unsupported"):
            with mock.patch.object(owner, "_host_command_dialect", return_value=host):
                self.assertIs(owner._recover_mislabeled_command_dialect(raw, resolution, primary)[1], primary)
        with mock.patch.object(owner, "_host_command_dialect", return_value="powershell"):
            unsupported = owner.CommandDialectResolution("unsupported", False)
            self.assertIs(owner._recover_mislabeled_command_dialect(raw, unsupported, primary)[1], primary)
            canonical_raw = "git push origin main"
            canonical = owner.parse_shell_command(canonical_raw, "posix")
            self.assertIs(owner._recover_mislabeled_command_dialect(canonical_raw, resolution, canonical)[1], canonical)
            foreign = owner.parse_shell_command("git push foreign other", "powershell").commands[0]
            with mock.patch.object(owner, "literal_direct_command", return_value=foreign):
                self.assertIs(owner._recover_mislabeled_command_dialect(raw, resolution, primary)[1], primary)
            # If both interpretations qualified, uniqueness must still refuse recovery.
            with mock.patch.object(owner, "literal_direct_command", side_effect=lambda parsed: parsed.commands[0]):
                self.assertIs(owner._recover_mislabeled_command_dialect(raw, resolution, primary)[1], primary)
            for tail in ("; echo other", " | sink", " && echo other", " &", " > sink", "\necho other"):
                mixed = raw + tail
                parsed = owner.parse_shell_command(mixed, "posix")
                result = owner._recover_mislabeled_command_dialect(mixed, resolution, parsed)
                self.assertEqual(result[0].dialect, "posix")
            for dynamic in ("& $git push origin main", "& 'literal-git' push origin $ref", "& 'literal-git' push origin `main", "& 'literal-git' pu`sh origin main", "& 'literal-git' push origin 'unterminated"):
                parsed = owner.parse_shell_command(dynamic, "posix")
                self.assertEqual(owner._recover_mislabeled_command_dialect(dynamic, resolution, parsed)[0].dialect, "posix")

    def test_compound_denial_has_only_safe_revision_and_parser_facts(self) -> None:
        module = _load_gate_module(CANONICAL_HOOK, "safe_compound_context")
        owner = module._a3_preflight
        canary = "SENSITIVE_COMMAND_PATH_ENV_CANARY"
        for raw, expected_branch in (("git push origin main; echo " + canary, "cardinality"),
                                     ("& 'C:/" + canary + "/git.exe' push origin main", "shell-boundary")):
            with synthetic_transcript([user("[approve-publication]")]) as transcript:
                with mock.patch.object(owner, "_host_command_dialect", return_value="posix"):
                    pre = owner.build_preflight({"tool_name": "Bash", "tool_input": {"command": raw, "workdir": str(REPO_ROOT)}, "cwd": str(REPO_ROOT), "transcript_path": str(transcript)})
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(module.compose_gate_result(pre), 0)
                payload = json.loads(output.getvalue())
                self.assertEqual(payload["hookSpecificOutput"]["permissionDecision"], "deny")
                reason = payload["hookSpecificOutput"]["permissionDecisionReason"]
                self.assertIn("PGG-COMPOUND-CONTEXT", reason)
                for token in ("branch=" + expected_branch, "operation=UNAVAILABLE", "dialect=posix", "commands=", "effective=", "eligible=", "literal=false", module.PUBLICATION_GATE_REVISION, owner.PUBLICATION_PREFLIGHT_REVISION):
                    self.assertIn(token, reason)
                self.assertNotIn(canary, reason)
                self.assertNotIn(str(REPO_ROOT), reason)
                self.assertNotIn(str(transcript), reason)

        registered = shlex.join(("git", *module.native_git_config_arguments(), "push", "origin", "HEAD:refs/heads/main"))
        pre = owner.build_preflight({"tool_name": "Bash", "tool_input": {"command": registered, "workdir": str(REPO_ROOT)}})
        with mock.patch.object(module, "_qualify_native_push_command", return_value=True) as qualify:
            self.assertTrue(module.evaluate_heavy(pre))
            qualify.assert_called_once_with(pre)

    def test_powershell_literal_call_operator_is_one_direct_dispatch(self) -> None:
        git = str(Path(shutil.which("git")).resolve(strict=True))
        root = str(REPO_ROOT.resolve())
        for script, module in self._modules("literal_PS_dispatch"):
            owner = module._a3_preflight
            commands = (
                "& '" + git + "' push origin 'HEAD:refs/heads/main'",
                "& " + chr(34) + git + chr(34) + " push 'origin' HEAD:refs/heads/main",
                "& git push origin main",
                "& '" + git + "' -C '" + root + "' push origin 'HEAD:refs/heads/main'",
                owner._serialize_powershell_literal((git, "-C", root, "push", "origin", "main")),
            )
            for command in commands:
                with self.subTest(script=script, command=command), mock.patch.object(owner, "_build_shell_lexical_state", wraps=owner._build_shell_lexical_state) as lexical:
                    parsed = owner.parse_shell_command(command, "powershell")
                    decision = owner.classify_generic_push(parsed)
                    self.assertEqual(decision.status, "PGG-ADMISSIBLE")
                    self.assertIs(owner.literal_direct_command(parsed), parsed.commands[0])
                    self.assertEqual(parsed.raw_command, command)
                    self.assertEqual(parsed.commands[0].boundary_before, "&")
                    lexical.assert_called_once()

    def test_powershell_call_operator_does_not_hide_other_effects(self) -> None:
        git = str(Path(shutil.which("git")).resolve(strict=True))
        base = "& '" + git + "' push origin main"
        commands = (base + "; Write-Output later", base + " | Out-Null", base + " && Write-Output later",
                    base + "\nWrite-Output later", base + " &", base + " > sink", "& " + base,
                    "&& " + base, "(" + base + ")", "& $git push origin main", "& '" + git + "' push origin $ref",
                    base.replace("push origin", "push --force origin"),
                    base.replace("push origin", "push --delete origin"))
        for script, module in self._modules("literal_PS_refusals"):
            for command in commands:
                with self.subTest(script=script, command=command):
                    owner = module._a3_preflight
                    self.assertNotEqual(owner.classify_generic_push(owner.parse_shell_command(command, "powershell")).status, "PGG-ADMISSIBLE")
            # Lexical recognition retains an empty source; the existing range
            # binding owner refuses deletion before any authoritative scan.
            deletion = base.replace("origin main", "origin :refs/heads/main")
            binding = owner.classify_generic_push(owner.parse_shell_command(deletion, "powershell")).binding
            self.assertIsNotNone(binding)
            with mock.patch.object(module, "_run_authoritative_scan") as forbidden:
                with self.assertRaises(module.PrRouteDenied) as refused:
                    module._resolve_generic_scan_binding(
                        *binding,
                        str(REPO_ROOT.resolve()), "git",
                    )
                self.assertEqual(refused.exception.failure_id, "PGG-RANGE-TIP-BINDING")
                forbidden.assert_not_called()
            canonical = shlex.join((git, "-C", str(REPO_ROOT.resolve()), "push", "origin", "main"))
            self.assertEqual(owner.classify_generic_push(owner.parse_shell_command(canonical, "posix")).status, "PGG-ADMISSIBLE")
            self.assertNotEqual(owner.classify_generic_push(owner.parse_shell_command(" " + canonical, "posix")).status, "PGG-ADMISSIBLE")


    def test_single_parse_projection_per_command_identity(self) -> None:
        command = "git push origin main"
        for script, module in self._modules("single_parse_projection"):
            with self.subTest(script=script):
                with mock.patch.object(
                    module._a3_preflight,
                    "_build_shell_lexical_state",
                    wraps=module._a3_preflight._build_shell_lexical_state,
                ) as lexical_build, mock.patch.object(
                    module._a3_preflight,
                    "_tokenize_shell_lexical_state",
                    wraps=module._a3_preflight._tokenize_shell_lexical_state,
                ) as tokenize:
                    parsed = module._a3_preflight.parse_shell_command(command, "posix")
                    pushes = module._a3_preflight.find_git_push_records(parsed)
                    module._a3_preflight.classify_generic_push(parsed)
                    parsed.scan_execution
                self.assertEqual(lexical_build.call_count, 1)
                self.assertEqual(tokenize.call_count, 1)
                self.assertIs(parsed.lexical.segments, parsed.segments)
                self.assertIs(pushes[0], parsed.pushes[0])
                self.assertEqual(parsed.strict_projection.status, "canonical")

    def test_strict_projection_uses_parser_owned_provenance(self) -> None:
        source = CANONICAL_HOOK.read_text(encoding="utf-8")
        self.assertNotIn("def _" + "decode_powershell_literal", source)
        for script, module in self._modules("strict_projection"):
            argv = (str(Path(sys.executable).resolve()), "push", "origin", "main")
            for dialect, command in (
                ("posix", shlex.join(argv)),
                ("powershell", module._a3_preflight._serialize_powershell_literal(argv)),
            ):
                with self.subTest(script=script, dialect=dialect):
                    parsed = module._a3_preflight.parse_shell_command(command, dialect)
                    self.assertEqual(parsed.strict_projection.status, "canonical")
                    self.assertEqual(parsed.strict_projection.argv, argv)

    def test_windows_bash_label_recovers_only_proved_powershell_literal(self) -> None:
        argv = (
            r"C:\Program Files\Git\cmd\git.exe",
            "push",
            "origin",
            "HEAD:refs/heads/feature",
        )
        for script, module in self._modules("windows_bash_label_recovery"):
            exact = module._a3_preflight._serialize_powershell_literal(argv)
            equivalent_literal = exact.replace("'push'", "push")
            with self.subTest(script=script):
                with synthetic_transcript([user("push now")]) as transcript_path, \
                     mock.patch.object(
                         module._a3_preflight,
                         "_host_command_dialect",
                         return_value="powershell",
                         create=True,
                     ):
                    recovered = module._a3_preflight.build_preflight({
                        "tool_name": "Bash",
                        "cwd": str(REPO_ROOT.parent),
                        "tool_input": {
                            "command": exact,
                            "workdir": str(REPO_ROOT),
                        },
                        "transcript_path": str(transcript_path),
                    })
                    literal_recovered = module._a3_preflight.build_preflight({
                        "tool_name": "Bash",
                        "cwd": str(REPO_ROOT.parent),
                        "tool_input": {
                            "command": equivalent_literal,
                            "workdir": str(REPO_ROOT),
                        },
                        "transcript_path": str(transcript_path),
                    })
                    simple = module._a3_preflight.build_preflight({
                        "tool_name": "Bash",
                        "cwd": str(REPO_ROOT.parent),
                        "tool_input": {
                            "command": "git push origin main",
                            "workdir": str(REPO_ROOT),
                        },
                        "transcript_path": str(transcript_path),
                    })
                self.assertEqual(recovered.dialect, "powershell")
                self.assertEqual(recovered.parsed.strict_projection.status, "canonical")
                self.assertEqual(
                    [record.kind for record in recovered.parsed.effective_publications.records],
                    ["DIRECT"],
                )
                self.assertEqual(literal_recovered.dialect, "powershell")
                self.assertEqual(module._a3_preflight.classify_generic_push(literal_recovered.parsed).status, "PGG-ADMISSIBLE")
                self.assertIs(module._a3_preflight.literal_direct_command(literal_recovered.parsed), literal_recovered.parsed.effective_publications.records[0].push.command)
                self.assertTrue(module._a3_preflight._is_exact_direct_literal(exact, recovered.parsed))
                self.assertFalse(module._a3_preflight._is_exact_direct_literal(equivalent_literal, literal_recovered.parsed))
                self.assertEqual(simple.dialect, "posix")


    def test_exec_command_prefers_absolute_tool_workdir_without_parent_fallback(self) -> None:
        argv = (
            str(Path(shutil.which("git") or "").resolve(strict=True)),
            "push", "origin", "HEAD:refs/heads/feature",
        )
        for script, module in self._modules("exec_workdir_binding"):
            command = (
                module._a3_preflight._serialize_powershell_literal(argv)
                if os.name == "nt"
                else shlex.join(argv)
            )
            with synthetic_transcript([user("push now")]) as transcript_path:
                base = {
                    "tool_name": "exec_command",
                    "cwd": str(REPO_ROOT.parent),
                    "transcript_path": str(transcript_path),
                }
                selected = module._a3_preflight.build_preflight({
                    **base,
                    "tool_input": {"command": command, "workdir": str(REPO_ROOT)},
                })
                fallback = module._a3_preflight.build_preflight({
                    **base,
                    "cwd": str(REPO_ROOT),
                    "tool_input": {"command": command},
                })
                relative = module._a3_preflight.build_preflight({
                    **base,
                    "tool_input": {"command": command, "workdir": "."},
                })
                file_path = module._a3_preflight.build_preflight({
                    **base,
                    "tool_input": {"command": command, "workdir": str(Path(__file__))},
                })
            self.assertEqual(selected.repository_workdir, str(REPO_ROOT.resolve()))
            self.assertEqual(fallback.repository_workdir, str(REPO_ROOT.resolve()))
            self.assertEqual(relative.reason_id, "PFP-DENY-KNOWN")
            self.assertEqual(relative.failure_id, "PRG-WORKDIR-INVALID")
            self.assertEqual(file_path.reason_id, "PFP-HEAVY")
            self.assertEqual(file_path.repository_workdir, str(Path(__file__)))

    def test_repository_workdir_proof_uses_exact_selected_cwd_and_rejects_nonrepo(self) -> None:
        git_exe = str(Path(shutil.which("git") or "").resolve(strict=True))
        for script, module in self._modules("repository_workdir_proof"):
            with self.subTest(script=script):
                with temporary_repository_workdir() as repository_workdir:
                    self.assertEqual(
                        module._prove_repository_root(module._normalize_repository_workdir(repository_workdir), git_exe),
                        repository_workdir,
                    )
                with tempfile.TemporaryDirectory() as directory, self.assertRaises(
                    module.PrRouteDenied
                ) as caught:
                    module._prove_repository_root(module._normalize_repository_workdir(directory), git_exe)
                self.assertEqual(caught.exception.failure_id, "PRG-WORKDIR-INVALID")
                with self.assertRaises(module.PrRouteDenied):
                    module._normalize_repository_workdir(str(Path(__file__)))

    def test_repository_workdir_normalizer_accepts_native_spellings(self) -> None:
        with tempfile.TemporaryDirectory(prefix="publication-workdir-") as directory:
            root = Path(directory) / "Repository"
            root.mkdir()
            canonical = str(root.resolve(strict=True))
            spellings = [canonical]
            if os.name == "nt":
                spellings.extend((canonical.replace("\\", "/"), canonical.swapcase()))
            traversal = str(root / ".." / root.name)

            for script, module in self._modules("repository_workdir_native_spellings"):
                for spelling in dict.fromkeys(spellings):
                    with self.subTest(script=script, spelling=spelling):
                        self.assertEqual(
                            module._normalize_repository_workdir(spelling), canonical
                        )
                with self.subTest(script=script, spelling=traversal):
                    with self.assertRaises(module.PrRouteDenied) as caught:
                        module._normalize_repository_workdir(traversal)
                    self.assertEqual(caught.exception.failure_id, "PRG-WORKDIR-INVALID")


    def test_generic_classifier_admits_only_absolute_literal_root_commands(self) -> None:
        with pr_literal_command_workspace() as workspace:
            target = workspace / "target"
            binary = workspace / "bin" / ("git.exe" if os.name == "nt" else "git")
            target.mkdir()
            binary.parent.mkdir()
            root = str(target.resolve(strict=True))
            executable = str(binary.resolve())
            for script, module in self._modules("generic_literal_root_classifier"):
                dialect = "powershell" if os.name == "nt" else "posix"
                argv = (
                    executable, "-C", root, "push", "origin",
                    "HEAD:refs/heads/feature",
                )
                command = (
                    module._a3_preflight._serialize_powershell_literal(argv)
                    if dialect == "powershell" else shlex.join(argv)
                )
                parsed = module._a3_preflight.parse_shell_command(command, dialect)
                decision = module._a3_preflight.classify_generic_push(parsed)
                with self.subTest(script=script, shape="literal-root"):
                    self.assertEqual(decision.status, "PGG-ADMISSIBLE")
                    self.assertEqual(
                        module._a3_preflight.absolute_literal_root_context(parsed),
                        (executable, root),
                    )
                    self.assertFalse(parsed.commands[0].trailing_linebreak_only)
                terminal = module._a3_preflight.parse_shell_command(command + "\n", dialect)
                with self.subTest(script=script, shape="literal-root-terminal-LF"):
                    self.assertTrue(terminal.commands[0].trailing_linebreak_only)
                    self.assertEqual(
                        terminal.commands[0].boundary_before, "&" if dialect == "powershell" else "start"
                    )
                    self.assertEqual(
                        module._a3_preflight.absolute_literal_root_context(terminal),
                        (executable, root),
                    )
                    self.assertEqual(
                        module._a3_preflight.classify_generic_push(terminal).status,
                        "PGG-ADMISSIBLE",
                    )

                for invalid_argv in (
                    ("git", "-C", root, "push", "origin", "HEAD:refs/heads/feature"),
                    (
                        executable, "-C", root, "-C", root, "push", "origin",
                        "HEAD:refs/heads/feature",
                    ),
                ):
                    invalid = (
                        module._a3_preflight._serialize_powershell_literal(invalid_argv)
                        if dialect == "powershell" else shlex.join(invalid_argv)
                    )
                    rejected = module._a3_preflight.classify_generic_push(
                        module._a3_preflight.parse_shell_command(invalid, dialect)
                    )
                    with self.subTest(script=script, shape=invalid_argv[:4]):
                        self.assertNotEqual(rejected.status, "PGG-ADMISSIBLE")


    def test_selected_root_excludes_forged_path_executables(self) -> None:
        for script, module in self._modules("selected_root_executable_exclusion"):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                forged = root / ("git.exe" if os.name == "nt" else "git")
                forged.write_bytes(b"forged\n")
                if os.name != "nt":
                    forged.chmod(0o700)
                with self.subTest(script=script), mock.patch.object(
                    module.shutil, "which", return_value=str(forged)
                ):
                    self.assertIsNone(module._resolve_executable("git", str(root)))


    def test_nested_child_uses_owned_span_without_join_reparse(self) -> None:
        command = "bash -c 'git push origin main'"
        for script, module in self._modules("nested_child_identity"):
            with self.subTest(script=script):
                with mock.patch.object(
                    module._a3_preflight,
                    "_build_shell_lexical_state",
                    wraps=module._a3_preflight._build_shell_lexical_state,
                ) as lexical_build, mock.patch.object(
                    module._a3_preflight,
                    "_tokenize_shell_lexical_state",
                    wraps=module._a3_preflight._tokenize_shell_lexical_state,
                ) as tokenize:
                    parsed = module._a3_preflight.parse_shell_command(command, "posix")
                self.assertEqual(lexical_build.call_count, 2)
                self.assertEqual(tokenize.call_count, 2)
                self.assertEqual(len(parsed.children), 1)
                child = parsed.children[0]
                self.assertEqual(child.raw_command, "git push origin main")
                self.assertEqual(child.identity.parent, parsed.identity)
                self.assertEqual(child.identity.depth, 1)
                self.assertTrue(module._a3_preflight.find_git_push_records(child))
                self.assertEqual(
                    [record.kind for record in parsed.effective_publications.records],
                    ["WRAPPER_CHILD"],
                )

        tree = ast.parse(
            (
                CANONICAL_HOOK.parent / "git_push_gate_preflight.py"
            ).read_text(encoding="utf-8")
        )
        names = {
            node.name for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.ClassDef))
        }
        self.assertNotIn("_project_child_" + "results", names)
        self.assertNotIn("_find_embedded_git_push_" + "records", names)
        self.assertNotIn("_project_embedded_" + "pushes", names)
        self.assertIn("WrapperArgvMachine", names)


    def test_unsupported_escape_retains_push_candidate(self) -> None:
        cases = (
            ("posix", "unsupported-physical-line", "g\\\r\nit push origin main", "SCG-UNSUPPORTED-ESCAPE"),
            ("posix", "dangling-marker", "git pus\\", "SCG-UNTERMINATED-ESCAPE"),
            ("powershell", "version-dependent-family", "g`u{69}t push origin main", "SCG-UNSUPPORTED-ESCAPE"),
            ("powershell", "dangling-marker", "git pus`", "SCG-UNTERMINATED-ESCAPE"),
        )
        for script, module in self._modules("unsupported_escape"):
            for dialect, fixture_name, command, expected_status in cases:
                with self.subTest(script=script, dialect=dialect, fixture=fixture_name):
                    parsed = module._a3_preflight.parse_shell_command(command, dialect)
                    self.assertEqual(parsed.status, expected_status)
                    self.assertTrue(parsed.candidates)
                    self.assertTrue(module._a3_preflight.find_git_push_records(parsed))

    def test_quote_and_data_states_do_not_normalize_executable_text(self) -> None:
        cases = (
            ("posix", "single-quoted", "'g\\\nit' push origin main"),
            ("posix", "heredoc-data", "cat <<EOF\ng\\\nit push origin hidden\nEOF\n"),
            ("powershell", "single-quoted", "'g`it' push origin main"),
            ("powershell", "here-string-data", "$x = @'\ng`it push origin hidden\n'@\n"),
            ("powershell", "block-comment-data", "<# g`it push origin hidden #>\nWrite-Output safe"),
        )
        for script, module in self._modules("normalization_data_state"):
            for dialect, fixture_name, command in cases:
                with self.subTest(script=script, dialect=dialect, fixture=fixture_name):
                    parsed = module._a3_preflight.parse_shell_command(command, dialect)
                    self.assertEqual(parsed.status, "SCG-PARSED")
                    self.assertFalse(module._a3_preflight.find_git_push_records(parsed))
                    self.assertFalse(parsed.normalizations)

    def test_escaped_syntax_does_not_create_shell_boundary(self) -> None:
        cases = (
            ("posix", "git pu\\\nsh origin main \\| cat \\> out", "|", ">"),
            ("powershell", "git pu`sh origin main `| cat `> out", "|", ">"),
        )
        for script, module in self._modules("literalized_syntax"):
            for dialect, command, *literal_values in cases:
                with self.subTest(script=script, dialect=dialect):
                    parsed = module._a3_preflight.parse_shell_command(command, dialect)
                    for value in literal_values:
                        atoms = [atom for atom in parsed.lexical.atoms if atom.value == value]
                        self.assertEqual(len(atoms), 1)
                        self.assertTrue(atoms[0].literalized)
                        self.assertFalse(atoms[0].operator_capable)
                    self.assertEqual(len(parsed.commands), 1)
                    self.assertEqual(parsed.commands[0].boundary_before, "start")
                    self.assertEqual(parsed.commands[0].boundary_after, "end")
                    self.assertEqual(len(module._a3_preflight.find_git_push_records(parsed)), 1)

    def test_normalization_requires_qualified_posix_static_literal_proof(self) -> None:
        cases = (
            ("posix", "git pu\\\nsh origin main", "PGG-ADMISSIBLE"),
            ("powershell", "git pu`sh origin main", "PGG-LEXICAL-NORMALIZATION"),
        )
        for script, module in self._modules("normalization_proof"):
            for dialect, command, expected in cases:
                with self.subTest(script=script, dialect=dialect):
                    parsed = module._a3_preflight.parse_shell_command(command, dialect)
                    self.assertEqual(len(module._a3_preflight.find_git_push_records(parsed)), 1)
                    self.assertEqual(
                        module._a3_preflight.classify_generic_push(parsed).status,
                        expected,
                    )


    def test_posix_multiline_quote_state_does_not_open_false_heredoc(self) -> None:
        module = _load_gate_module(CANONICAL_HOOK, "posix_multiline_quote_state")
        preflight = module._a3_preflight
        quoted_shift = "python -c @'\nx = 1 << 2\n'@"
        parsed = preflight.parse_shell_command(quoted_shift, "posix")
        result = preflight.build_preflight(
            {
                "tool_name": "Bash",
                "cwd": str(REPO_ROOT),
                "tool_input": {"command": quoted_shift, "workdir": str(REPO_ROOT)},
            }
        )
        self.assertEqual(parsed.status, "SCG-PARSED")
        self.assertFalse(preflight.find_git_push_records(parsed))
        self.assertEqual(result.reason_id, "PFP-ALLOW-NON-PUSH")

        for command in (
            "python -c @'\nx = 1 << 2\n'@\ngit push origin main",
            "printf '<<EOF'\ngit push origin main",
            "printf \\<<EOF\ngit push origin main",
            "# <<EOF\ngit push origin main",
        ):
            with self.subTest(command=command):
                candidate = preflight.parse_shell_command(command, "posix")
                self.assertTrue(preflight.find_git_push_records(candidate))


    def test_parsed_powershell_compound_nonpublication_is_not_parse_uncertain(self) -> None:
        module = _load_gate_module(CANONICAL_HOOK, "parsed_nonpublication_preflight")
        preflight = module._a3_preflight
        command = "$code = @'\n['git', 'cat-file', 'blob', 'HEAD:fixture']\n'@\npython -c $code"
        parsed = preflight.parse_shell_command(command, "powershell")
        result = preflight.build_preflight(
            {
                "tool_name": "PowerShell",
                "cwd": str(REPO_ROOT),
                "tool_input": {"command": command, "workdir": str(REPO_ROOT)},
            }
        )

        self.assertEqual(parsed.status, "SCG-PARSED")
        self.assertFalse(preflight.find_git_push_records(parsed))
        self.assertFalse(parsed.candidates)
        self.assertEqual((result.outcome, result.reason_id), ("ALLOW_FINAL", "PFP-ALLOW-NON-PUSH"))

        for candidate in (
            "$code = @'\ngit cat-file blob HEAD:fixture\n'@\ngit push origin main",
            "$code = @'\ngit push origin hidden",
            "git push origin main",
            "python -c \"print('x')\"; git push origin main",
        ):
            with self.subTest(command=candidate):
                candidate_parsed = preflight.parse_shell_command(candidate, "powershell")
                candidate_result = preflight.build_preflight(
                    {
                        "tool_name": "PowerShell",
                        "cwd": str(REPO_ROOT),
                        "tool_input": {"command": candidate, "workdir": str(REPO_ROOT)},
                    }
                )
                self.assertTrue(
                    preflight.find_git_push_records(candidate_parsed)
                    or candidate_parsed.candidates
                )
                self.assertNotEqual(candidate_result.reason_id, "PFP-ALLOW-NON-PUSH")


    def test_invocation_record_retains_prefix_global_and_repository_provenance(self) -> None:
        cases = (
            ("git push origin main", (), (), "ambient"),
            ("FOO=1 git push origin main", ("FOO=1",), (), "ambient"),
            ("GIT_DIR=.git2 git push origin main", ("GIT_DIR=.git2",), (), "redirected"),
            ("git -c color.ui=false push origin main", (), ("-c", "color.ui=false"), "ambient"),
            ("git --config-env=remote.origin.url=URL_ENV push origin main", (), ("--config-env=remote.origin.url=URL_ENV",), "ambient"),
            ("git -C .. push origin main", (), ("-C", ".."), "redirected"),
            ("git --git-dir=.other push origin main", (), ("--git-dir=.other",), "redirected"),
            ("git --work-tree .. push origin main", (), ("--work-tree", ".."), "redirected"),
            ("git push --repo=elsewhere origin main", (), (), "redirected"),
        )
        for script, module in self._modules("provenance"):
            for command, env_prefix, global_options, repository_context in cases:
                with self.subTest(script=script, command=command):
                    parsed = module._a3_preflight.parse_shell_command(command, "posix")
                    pushes = module._a3_preflight.find_git_push_records(parsed)
                    self.assertEqual(len(pushes), 1)
                    self.assertEqual(pushes[0].environment_assignments, env_prefix)
                    self.assertEqual(pushes[0].git_global_options, global_options)
                    self.assertEqual(pushes[0].repository_context, repository_context)

    def test_command_records_retain_exact_spans_boundaries_and_control_prefixes(self) -> None:
        command = "cd .. && ! git push origin main"
        for script, module in self._modules("record_spans"):
            with self.subTest(script=script):
                parsed = module._a3_preflight.parse_shell_command(command, "posix")
                self.assertEqual(parsed.status, "SCG-PARSED")
                self.assertEqual(len(parsed.commands), 2)
                self.assertEqual(
                    tuple(command[start:end] for start, end in (item.source_span for item in parsed.commands)),
                    ("cd ..", "! git push origin main"),
                )
                self.assertEqual(parsed.commands[0].boundary_after, "&&")
                self.assertEqual(parsed.commands[1].boundary_before, "&&")
                self.assertEqual(parsed.commands[1].control_keywords, ("!",))
                self.assertEqual(module._a3_preflight.classify_generic_push(parsed).status, "PGG-COMPOUND-CONTEXT")
                self.assertEqual(
                    module._a3_preflight.resolve_command_dialect("shell_command").dialect,
                    "powershell" if module.os.name == "nt" else "posix",
                )


    def test_push_option_arity_value_and_negation_matrix(self) -> None:
        cases = (
            ("git push -o --dry-run origin main", "GPO-PARSED", "DRY-NOT-CREDITABLE", ("origin", "main")),
            ("git push --push-option=--dry-run origin main", "GPO-PARSED", "DRY-NOT-CREDITABLE", ("origin", "main")),
            ("git push --no-push-option --dry-run origin main", "GPO-PARSED", "DRY-NOT-CREDITABLE", ("origin", "main")),
            ("git push --exec=--dry-run origin main", "GPO-PARSED", "DRY-NOT-CREDITABLE", ("origin", "main")),
            ("git push --no-exec --dry-run origin main", "GPO-PARSED", "DRY-NOT-CREDITABLE", ("origin", "main")),
            ("git push --receive-pack=--dry-run origin main", "GPO-PARSED", "DRY-NOT-CREDITABLE", ("origin", "main")),
            ("git push --no-receive-pack --dry-run origin main", "GPO-PARSED", "DRY-NOT-CREDITABLE", ("origin", "main")),
            ("git push --repo=--dry-run origin main", "GPO-PARSED", "DRY-NOT-CREDITABLE", ("origin", "main")),
            ("git push --no-repo --dry-run origin main", "GPO-PARSED", "DRY-NOT-CREDITABLE", ("origin", "main")),
            ("git push --recurse-submodules check origin main", "GPO-PARSED", "DRY-NOT-CREDITABLE", ("origin", "main")),
            ("git push --recurse-submodules=on-demand origin main", "GPO-PARSED", "DRY-NOT-CREDITABLE", ("origin", "main")),
            ("git push --no-recurse-submodules no origin main", "GPO-PARSED", "DRY-NOT-CREDITABLE", ("no", "origin", "main")),
            ("git push --force-with-lease origin main", "GPO-PARSED", "DRY-NOT-CREDITABLE", ("origin", "main")),
            ("git push --force-with-lease=--dry-run origin main", "GPO-PARSED", "DRY-NOT-CREDITABLE", ("origin", "main")),
            ("git push --signed=--dry-run origin main", "GPO-PARSED", "DRY-NOT-CREDITABLE", ("origin", "main")),
            ("git push --no-progress origin main", "GPO-PARSED", "DRY-NOT-CREDITABLE", ("origin", "main")),
            ("git push --dry-run origin main", "GPO-PARSED", "DRY-ENABLED", ("origin", "main")),
            ("git push --dry-run --no-dry-run origin main", "GPO-PARSED", "DRY-INDETERMINATE", ("origin", "main")),
            ("git push -- --dry-run origin main", "GPO-PARSED", "DRY-NOT-CREDITABLE", ("--dry-run", "origin", "main")),
            ("git push --push-option", "GPO-MISSING-VALUE", "DRY-INDETERMINATE", ()),
            ("git push --recurse-submodules=invalid origin main", "GPO-AMBIGUOUS", "DRY-INDETERMINATE", ("origin", "main")),
            ("git push --qui origin main", "GPO-UNKNOWN", "DRY-INDETERMINATE", ("origin", "main")),
        )
        for script, module in self._modules("option_arity"):
            for command, option_status, dry_state, operands in cases:
                with self.subTest(script=script, command=command):
                    parsed = module._a3_preflight.parse_shell_command(command, "posix")
                    pushes = module._a3_preflight.find_git_push_records(parsed)
                    self.assertEqual(len(pushes), 1)
                    self.assertEqual(pushes[0].option_status, option_status)
                    self.assertEqual(pushes[0].dry_run_state, dry_state)
                    self.assertEqual(pushes[0].positionals, operands)


class TestPublicationSafetyTrustedScanR2(unittest.TestCase):
    """The gate owns fresh scanner execution and validates its result."""

    def _module(self, suffix: str):
        return _load_gate_module(CANONICAL_HOOK, "publication_r2_" + suffix)

    def _pending(self, module, binding, argv):
        interpreter = module._interpreter_identity()
        root = module.PathComponentIdentity(".", "directory", ())
        closure = module.CanonicalSourceClosure(
            module.SOURCE_LAYOUTS[0], root, (root,), (), "a" * 64, (),
            "b" * 64, interpreter,
            module.RootLocatorIdentity("gate.py", ".", "directory", (), None, ".", (), "gate.py", ()),
        )
        payload = b""
        captured_review = module.CapturedReviewPayload(
            module.CapturedReviewModules(object(), object(), ()),
            {}, "c" * 64,
            {"status": "not-requested", "repository": None, "diagnostic": "not-needed"},
            None, False, payload, hashlib.sha256(payload).hexdigest(),
        )
        return module.PendingScanInvocation(
            "invocation", "attempt", binding, closure,
            interpreter, tuple(argv), object(), captured_review,
        )


    def test_gate_denial_registry_covers_provenance_execution_and_redaction(self) -> None:
        module = self._module("denials")
        expected = {
            "PGG-SCAN-PROVENANCE",
            "PRG-SCAN-PROVENANCE",
            "PGG-SCAN-IDENTITY-DRIFT",
            "PRG-SCAN-IDENTITY-DRIFT",
            "PGG-SCAN-EXECUTION",
            "PRG-SCAN-EXECUTION",
            "PGG-SCAN-FINDING",
            "PRG-SCAN-FINDING",
            "PGG-SCAN-REFUSAL",
            "PRG-SCAN-REFUSAL",
        }
        self.assertTrue(hasattr(module, "SCAN_DENIAL_REASONS"), "R2-GATE-DENIAL-REGISTRY")
        if not hasattr(module, "SCAN_DENIAL_REASONS"):
            return
        self.assertTrue(expected.issubset(module.SCAN_DENIAL_REASONS))
        forbidden_fields = ("path", "command", "remote", "destination", "stdout", "stderr")
        for failure_id in expected:
            with self.subTest(failure_id=failure_id):
                rendered = module.SCAN_DENIAL_REASONS[failure_id].casefold()
                self.assertFalse(any(field + "=" in rendered for field in forbidden_fields))

    def test_gate_owned_snapshot_executes_real_sibling_for_bound_range(self) -> None:
        module = self._module("real_snapshot")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            remote = root / "remote.git"
            repo = root / "repo"
            subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            for key, value in (("user.name", "T"), ("user.email", "t@t")):
                subprocess.run(["git", "-C", str(repo), "config", key, value], check=True)
            (repo / "seed.txt").write_text("clean seed\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "seed.txt"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "clean seed"], check=True)
            subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", str(remote)], check=True)
            subprocess.run(["git", "-C", str(repo), "push", "-q", "origin", "HEAD:refs/heads/main"], check=True)
            (repo / "next.txt").write_text("clean next\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "next.txt"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "clean next"], check=True)
            head = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "HEAD"],
                check=True, capture_output=True, text=True, encoding="utf-8",
            ).stdout.strip()
            previous = Path.cwd()
            binding = module.PushScanBinding(
                "generic", "origin", "refs/heads/main", head, head
            )
            git_exe = str(Path(shutil.which("git") or "").resolve(strict=True))
            forged_bin = root / "forged-bin"
            forged_bin.mkdir()
            forged = forged_bin / ("git.exe" if os.name == "nt" else "git")
            forged.write_bytes(b"forged\n")
            if os.name != "nt":
                forged.chmod(0o700)
            with mock.patch.dict(os.environ, {"PATH": str(forged_bin)}):
                observation = module._run_authoritative_scan(
                    binding, str(repo.resolve()), git_exe
                )
            self.assertEqual(Path.cwd(), previous)
        self.assertEqual(type(observation).__name__, "ConsumedAuthoritativeEvidence")
        self.assertEqual(observation.parsed_outcome.kind, "valid-v3")
        self.assertEqual(observation.parsed_outcome.receipt.commits, 1)
        self.assertEqual(
            observation.parsed_outcome.receipt.destination,
            "refs/heads/main",
        )
        self.assertEqual(observation.parsed_outcome.receipt.source, head)
        self.assertEqual(observation.parsed_outcome.receipt.tip, head)
        range_tip_index = observation.execution.launched.exact_argv.index(
            "--range-source"
        )
        self.assertEqual(
            observation.execution.launched.exact_argv[range_tip_index + 1],
            head,
        )
        self.assertTrue(observation.consumption_id)
        self.assertEqual(observation.execution.pending.state, module.PendingState.CONSUMED)

    def test_gate_owned_snapshot_authorizes_sha256_repository_range(self) -> None:
        module = self._module("real_snapshot_sha256")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            remote = root / "remote.git"
            repo = root / "repo"
            subprocess.run(
                ["git", "init", "-q", "--bare", "--object-format=sha256", str(remote)],
                check=True,
            )
            subprocess.run(
                ["git", "init", "-q", "--object-format=sha256", str(repo)], check=True
            )
            for key, value in (("user.name", "T"), ("user.email", "t@t")):
                subprocess.run(["git", "-C", str(repo), "config", key, value], check=True)
            (repo / "seed.txt").write_text("clean seed\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "seed.txt"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "clean seed"], check=True)
            subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", str(remote)], check=True)
            subprocess.run(["git", "-C", str(repo), "push", "-q", "origin", "HEAD:refs/heads/main"], check=True)
            (repo / "next.bin").write_bytes(b"\0\1\2")
            subprocess.run(["git", "-C", str(repo), "add", "next.bin"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "clean next"], check=True)
            head = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "HEAD"],
                check=True, capture_output=True, text=True, encoding="utf-8",
            ).stdout.strip()
            self.assertEqual(len(head), 64)
            binding = module._resolve_generic_scan_binding(
                "origin", "refs/heads/main", "HEAD", str(repo.resolve()),
                str(Path(shutil.which("git") or "").resolve(strict=True)),
            )
            observation = module._run_authoritative_scan(
                binding,
                str(repo.resolve()),
                str(Path(shutil.which("git") or "").resolve(strict=True)),
            )

        self.assertEqual(type(observation).__name__, "ConsumedAuthoritativeEvidence")
        self.assertEqual(observation.parsed_outcome.kind, "valid-v3")
        self.assertEqual(observation.parsed_outcome.receipt.commits, 1)
        self.assertEqual(observation.parsed_outcome.receipt.source, head)
        self.assertEqual(observation.parsed_outcome.receipt.tip, head)
        self.assertEqual(observation.execution.pending.state, module.PendingState.CONSUMED)


    def test_snapshot_boundary_rejects_alternate_hard_link(self) -> None:
        module = self._module("hardlink")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            scripts = root / "scripts"
            hooks = root / "hooks"
            scripts.mkdir()
            hooks.mkdir()
            gate = scripts / "check-git-push-gate.py"
            backing = scripts / "backing.py"
            scanner = scripts / "check-publication-safety.py"
            gate.write_text("# gate fixture\n", encoding="utf-8")
            (scripts / "hook_common.py").write_text("# common fixture\n", encoding="utf-8")
            (hooks / "check-machine-local-path.py").write_text(
                "def find_machine_paths(value): return []\n", encoding="utf-8"
            )
            backing.write_text("# scanner fixture\n", encoding="utf-8")
            os.link(backing, scanner)
            helpers = scripts / "process_supervision"
            helpers.mkdir()
            for filename in ("posix_process_group.py", "windows_job.py"):
                (helpers / filename).write_bytes(
                    (REPO_ROOT / "scripts/process_supervision" / filename).read_bytes()
                )
            (scripts / "publication_review_policy.py").write_bytes(
                CANONICAL_HOOK.with_name("publication_review_policy.py").read_bytes()
            )
            (scripts / "linked_runtime_subroots.py").write_bytes(
                (REPO_ROOT / "scripts" / "linked_runtime_subroots.py").read_bytes()
            )
            original_file = module.__file__
            try:
                module.__file__ = str(gate)
                with self.assertRaises(ValueError):
                    module._capture_source_closure()
            finally:
                module.__file__ = original_file

    def test_authoritative_child_timeout_and_output_overflow_reap_workers(self) -> None:
        module = self._module("child_bounds")
        binding = module.PushScanBinding(
            "generic", "origin", "refs/heads/main", "1" * 40, "1" * 40
        )
        before = {thread.ident for thread in threading.enumerate()}
        original_timeout = module.SCAN_TIMEOUT_SECONDS
        original_cap = module.SCAN_OUTPUT_BYTE_CAP
        with temporary_repository_workdir() as repository_workdir:
            try:
                module.SCAN_TIMEOUT_SECONDS = 0.1
                pending = self._pending(
                    module, binding,
                    (sys.executable, "-c", "import time; time.sleep(60)"),
                )
                _invocation, timed_rows = module._run_snapshot_child(
                    pending, b"", repository_workdir
                )
                timed = timed_rows[0]
                self.assertFalse(timed.bounded_completion)
                self.assertTrue(timed.settlement.complete)

                module.SCAN_TIMEOUT_SECONDS = 2.0
                module.SCAN_OUTPUT_BYTE_CAP = 128
                pending = self._pending(
                    module, binding,
                    (sys.executable, "-c", "import sys; sys.stdout.write('x'*4096)"),
                )
                _invocation, overflow_rows = module._run_snapshot_child(
                    pending, b"", repository_workdir
                )
                overflow = overflow_rows[0]
                self.assertFalse(overflow.bounded_completion)
                self.assertTrue(overflow.settlement.complete)
            finally:
                module.SCAN_TIMEOUT_SECONDS = original_timeout
                module.SCAN_OUTPUT_BYTE_CAP = original_cap
        after = [
            thread for thread in threading.enumerate()
            if thread.ident not in before and thread.is_alive()
        ]
        self.assertEqual(after, [])


class TestPublicationComponentRoot(unittest.TestCase):
    @contextlib.contextmanager
    def component(self):
        with tempfile.TemporaryDirectory(prefix="publication-component-") as directory:
            root = Path(directory)
            physical = root / "ordinary-component"
            sources = (
                ("scripts/check-git-push-gate.py", CANONICAL_HOOK),
                ("scripts/hook_common.py", CANONICAL_HOOK.with_name("hook_common.py")),
                ("scripts/check-publication-safety.py", CANONICAL_HOOK.with_name("check-publication-safety.py")),
                ("hooks/check-machine-local-path.py", CANONICAL_HOOK.parent.parent / "hooks/check-machine-local-path.py"),
                ("scripts/process_supervision/posix_process_group.py", REPO_ROOT / "scripts/process_supervision/posix_process_group.py"),
                ("scripts/process_supervision/windows_job.py", REPO_ROOT / "scripts/process_supervision/windows_job.py"),
                ("scripts/publication_review_policy.py", CANONICAL_HOOK.with_name("publication_review_policy.py")),
                ("scripts/linked_runtime_subroots.py", REPO_ROOT / "scripts/linked_runtime_subroots.py"),
            )
            for relative, source in sources:
                target = physical / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
            module = _load_gate_module(CANONICAL_HOOK, "publication_component_" + secrets.token_hex(8))
            yield module, root, physical

    def link_root(self, alias, target):
        if os.name == "nt":
            import _winapi
            _winapi.CreateJunction(str(target), str(alias))
        else:
            alias.symlink_to(target, target_is_directory=True)

    def unlink_root(self, alias):
        if os.name == "nt":
            alias.rmdir()
        else:
            alias.unlink()

    def test_complete_component_and_selected_root_alias_capture_same_physical_gate(self):
        with self.component() as (module, root, physical):
            alias = root / "logical-component"
            self.link_root(alias, physical)
            try:
                for selected in (physical, alias):
                    module.__file__ = str(selected / "scripts/check-git-push-gate.py")
                    fds, closure = module._capture_source_closure()
                    try:
                        self.assertEqual(closure.layout.name, "component")
                        self.assertEqual(closure.root_locator.physical_root, str(physical.resolve()))
                        self.assertEqual(closure.root_locator.gate_identity, closure.nodes[0].file_identity)
                        self.assertEqual(closure.root_locator.raw_target, os.readlink(alias) if selected == alias else None)
                        self.assertEqual(closure.root_locator.kind, "junction" if selected == alias and os.name == "nt" else "symlink" if selected == alias else "directory")
                        self.assertIs(module._recheck_source_closure(fds, closure), closure)
                        captured_modules = module._load_captured_review_modules(closure)
                        try:
                            snapshot = {
                                "schemaVersion": 1, "status": "absent", "origin": None,
                                "rawBase64": None, "rawSha256": None, "diagnostic": "absent",
                            }
                            observation = {
                                "status": "not-requested", "repository": None,
                                "diagnostic": "not-needed",
                            }
                            snapshot_id = captured_modules.policy_module.H(
                                "orchestrarium.publication-review.snapshot.v1", snapshot
                            )
                            payload = module._closure_payload(
                                closure,
                                {
                                    "schemaVersion": 1,
                                    "repositoryObservation": observation,
                                    "snapshot": snapshot,
                                    "snapshotId": snapshot_id,
                                },
                                captured_modules.policy_module.C,
                            )
                            payload_data = json.loads(payload.decode("ascii"))
                            self.assertEqual(payload_data["payloadVersion"], 1)
                            self.assertEqual(
                                set(payload_data["sources"]),
                                {node.role for node in closure.nodes if node.role != "gate"},
                            )
                            self.assertEqual(payload_data["review"]["snapshotId"], snapshot_id)
                            self.assertNotIn("root_locator", payload_data)
                        finally:
                            module._release_captured_review_modules(captured_modules)
                    finally:
                        for fd in fds: os.close(fd)
            finally:
                self.unlink_root(alias)

    def test_selected_root_retarget_and_same_target_replacement_deny(self):
        with self.component() as (module, root, physical):
            second = root / "second-complete-component"
            shutil.copytree(physical, second)
            alias = root / "logical-component"
            for target in (second, physical):
                self.link_root(alias, physical)
                module.__file__ = str(alias / "scripts/check-git-push-gate.py")
                fds, closure = module._capture_source_closure()
                old = root / "retained-alias"
                try:
                    alias.rename(old)
                    self.link_root(alias, target)
                    self.assertNotEqual(os.lstat(alias).st_ino, closure.root_locator.locator_identity[1])
                    with self.assertRaises(ValueError):
                        module._recheck_source_closure(fds, closure)
                finally:
                    for fd in fds: os.close(fd)
                    self.unlink_root(alias)
                    self.unlink_root(old)

    def test_capture_window_root_replacement_refuses_and_closes_every_descriptor(self):
        with self.component() as (module, root, physical):
            alias = root / "logical-component"
            old = root / "retained-alias"
            self.link_root(alias, physical)
            module.__file__ = str(alias / "scripts/check-git-push-gate.py")
            acquired = []
            capture_node = module._capture_source_node
            capture_directory = module._capture_directory
            capture_interpreter = module._capture_interpreter_handle
            def node(path, role, *, owned_fds=None):
                result = capture_node(path, role, owned_fds=owned_fds)
                acquired.append(result[0])
                if role == "scanner":
                    alias.rename(old)
                    self.link_root(alias, physical)
                return result
            def directory(path, *, owned_fds=None):
                result = capture_directory(path, owned_fds=owned_fds)
                acquired.append(result[0])
                return result
            def interpreter(identity, *, owned_fds=None):
                fd = capture_interpreter(identity, owned_fds=owned_fds)
                acquired.append(fd)
                return fd
            binding = module.PushScanBinding("generic", "origin", "refs/heads/topic", "a" * 40, "a" * 40)
            try:
                with mock.patch.object(module, "_capture_source_node", side_effect=node), \
                     mock.patch.object(module, "_capture_directory", side_effect=directory), \
                     mock.patch.object(module, "_capture_interpreter_handle", side_effect=interpreter), \
                     mock.patch.object(module, "_run_snapshot_child") as child:
                    with self.assertRaises(module.PrRouteDenied) as denied:
                        module._run_authoritative_scan(binding, str(root), "unused-before-child")
                    self.assertEqual(denied.exception.failure_id, "PGG-SCAN-PROVENANCE")
                    child.assert_not_called()
                self.assertTrue(acquired)
                for fd in acquired:
                    with self.assertRaises(OSError): os.fstat(fd)
            finally:
                self.unlink_root(alias)
                if old.exists(): self.unlink_root(old)

    @unittest.skipUnless(os.name == "nt", "Windows junction raw-target mutation")
    def test_native_root_raw_target_change_preserving_terminal_denies(self):
        import ctypes
        import struct
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        create = kernel.CreateFileW
        create.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
        create.restype = wintypes.HANDLE
        control = kernel.DeviceIoControl
        control.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID)
        control.restype = wintypes.BOOL
        close = kernel.CloseHandle
        close.argtypes = (wintypes.HANDLE,)
        close.restype = wintypes.BOOL
        with self.component() as (module, root, physical):
            alias = root / "logical-component"
            self.link_root(alias, physical)
            module.__file__ = str(alias / "scripts/check-git-push-gate.py")
            fds, closure = module._capture_source_closure()
            handle = None
            try:
                handle = create(str(alias), 0x40000000, 7, None, 3, 0x02200000, None)
                if handle == ctypes.c_void_p(-1).value:
                    handle = None
                    raise ctypes.WinError(ctypes.get_last_error())
                # Mount-point reparse wire format: offsets/lengths are UTF-16
                # byte units, followed by the substitute and display strings.
                substitute = ("\\??\\" + str(physical).upper()).encode("utf-16-le")
                display = str(physical).encode("utf-16-le")
                paths = substitute + b"\0\0" + display + b"\0\0"
                data = struct.pack("<IHHHHHH", stat.IO_REPARSE_TAG_MOUNT_POINT, 8 + len(paths), 0, 0, len(substitute), len(substitute) + 2, len(display)) + paths
                buffer = ctypes.create_string_buffer(data)
                returned = wintypes.DWORD()
                if not control(handle, 0x000900A4, buffer, len(data), None, 0, ctypes.byref(returned), None):
                    raise ctypes.WinError(ctypes.get_last_error())
                current = module._observe_root_locator(Path(module.__file__), closure.layout, alias)
                self.assertEqual(current.locator_identity[:2], closure.root_locator.locator_identity[:2])
                self.assertEqual(current.physical_root, closure.root_locator.physical_root)
                self.assertEqual(current.gate_identity, closure.root_locator.gate_identity)
                self.assertNotEqual(current.raw_target, closure.root_locator.raw_target)
                with self.assertRaises(ValueError): module._recheck_source_closure(fds, closure)
            finally:
                if handle is not None: self.assertTrue(close(handle))
                for fd in fds: os.close(fd)
                self.unlink_root(alias)

    def test_closing_physical_recheck_reobserves_locator(self):
        with self.component() as (module, root, physical):
            alias = root / "logical-component"
            old = root / "retained-alias"
            self.link_root(alias, physical)
            module.__file__ = str(alias / "scripts/check-git-push-gate.py")
            fds, closure = module._capture_source_closure()
            original_interpreter = module._interpreter_identity
            def replace_after_physical_check():
                alias.rename(old)
                self.link_root(alias, physical)
                return original_interpreter()
            try:
                with mock.patch.object(module, "_interpreter_identity", side_effect=replace_after_physical_check), self.assertRaises(ValueError):
                    module._recheck_source_closure(fds, closure)
            finally:
                for fd in fds: os.close(fd)
                self.unlink_root(alias)
                if old.exists(): self.unlink_root(old)

    def test_declared_source_layouts_and_incomplete_component_packages(self):
        module = _load_gate_module(CANONICAL_HOOK, "publication_incomplete_component")
        declared = (
            (CANONICAL_HOOK, "universal", REPO_ROOT / "scripts"),
            (
                HOOKS[0],
                "claude-source",
                REPO_ROOT,
            ),
            (
                HOOKS[1],
                "codex-source",
                REPO_ROOT,
            ),
        )
        for projection, expected_layout, expected_root in declared:
            module.__file__ = str(projection)
            with self.subTest(projection=projection):
                layout, selected_root = module._layout_for_gate(Path(module.__file__))
                self.assertEqual(layout.name, expected_layout)
                self.assertEqual(selected_root, expected_root)
        with self.component() as (module, root, physical):
            for invalid in (physical / "check-git-push-gate.py", physical / "scripts/other.py"):
                module.__file__ = str(invalid)
                with self.assertRaises(ValueError): module._capture_source_closure()
            module.__file__ = str(physical / "scripts/check-git-push-gate.py")
            layout, _root = module._layout_for_gate(Path(module.__file__))
            for role, relative in layout.role_paths:
                path = physical / relative
                source = path.read_bytes()
                path.unlink()
                try:
                    with self.subTest(missing_role=role), self.assertRaises(OSError):
                        module._capture_source_closure()
                finally:
                    path.write_bytes(source)

    def test_opaque_root_and_wrong_logical_gate_relation_refuse(self):
        with self.component() as (module, root, physical):
            module.__file__ = str(physical / "scripts/check-git-push-gate.py")
            actual_lstat = os.lstat
            def opaque_root(path, *args, **kwargs):
                if Path(path) == physical:
                    return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400, st_reparse_tag=0x80000023)
                return actual_lstat(path, *args, **kwargs)
            with mock.patch.object(os, "lstat", side_effect=opaque_root), self.assertRaises(ValueError):
                module._capture_source_closure()
            actual_identity = module._regular_identity
            calls = 0
            def wrong_gate(path, **kwargs):
                nonlocal calls
                identity = actual_identity(path, **kwargs)
                calls += 1
                return identity + (99,) if calls == 1 else identity
            with mock.patch.object(module, "_regular_identity", side_effect=wrong_gate), self.assertRaises(ValueError):
                module._capture_source_closure()

    def test_below_root_link_and_hardlinked_file_remain_refused(self):
        with self.component() as (module, root, physical):
            module.__file__ = str(physical / "scripts/check-git-push-gate.py")
            hooks = physical / "hooks"
            outside = root / "outside-hooks"
            hooks.rename(outside)
            self.link_root(hooks, outside)
            try:
                with self.assertRaises(ValueError): module._capture_source_closure()
            finally:
                self.unlink_root(hooks)
                outside.rename(hooks)
            scanner = physical / "scripts/check-publication-safety.py"
            other = root / "scanner-hardlink.py"
            os.link(scanner, other)
            with self.assertRaises(ValueError): module._capture_source_closure()


class TestPublicationSafetyTrustedScanR3(unittest.TestCase):
    """R3 RED/GREEN guards for closure, correlation, cleanup, and C6 truth."""

    def _module(self, suffix: str):
        return _load_gate_module(CANONICAL_HOOK, "publication_r3_" + suffix)

    def test_push_gate_projections_match_canonical_bytes(self) -> None:
        canonical = CANONICAL_HOOK.read_bytes()
        for projection in HOOKS:
            with self.subTest(projection=projection):
                self.assertEqual(canonical, projection.read_bytes())

    def _closure(self, module):
        interpreter = module._interpreter_identity()
        root = module.PathComponentIdentity(".", "directory", ())
        return module.CanonicalSourceClosure(
            module.SOURCE_LAYOUTS[0], root, (root,), (), "a" * 64, (),
            "b" * 64, interpreter,
            module.RootLocatorIdentity("gate.py", ".", "directory", (), None, ".", (), "gate.py", ()),
        )

    def test_frozen_bootstrap_injects_held_windows_job_module(self) -> None:
        import base64

        module = self._module("windows_job_bootstrap")
        snapshot_id = "f" * 64
        source = {
            "hook_common": b"",
            "classifier": b"def find_machine_paths(*args, **kwargs): return []\n",
            "posix_helper": b"",
            "windows_job": b"WINDOWS_JOB_SENTINEL = True\n",
            "linked_runtime_subroots": b"LINKED_SUBROOT_SENTINEL = True\n",
            "publication_review_policy": (
                b"POLICY_MODULE_CONTRACT_ID = 'orchestrarium.publication-review-policy.module.v1'\n"
                b"POLICY_MODULE_KEY = '_orchestrarium_publication_review_policy_v1'\n"
                b"POLICY_INJECTION_KEY = '__injected_review_policy_module__'\n"
                + f"def H(domain, value): return '{snapshot_id}'\n".encode("ascii")
            ),
            "scanner": (
                b"import sys\n"
                b"assert __injected_windows_job_module__.__name__ == "
                b"'_orchestrarium_windows_job_v1'\n"
                b"assert __injected_windows_job_module__.WINDOWS_JOB_SENTINEL\n"
                b"assert __injected_review_policy_module__ is "
                b"sys.modules['_orchestrarium_publication_review_policy_v1']\n"
                b"assert __injected_review_policy_module__.POLICY_MODULE_CONTRACT_ID == "
                b"'orchestrarium.publication-review-policy.module.v1'\n"
                b"assert __injected_review_policy_snapshot__['status'] == 'absent'\n"
                b"assert __injected_review_repository_observation__['status'] == 'not-requested'\n"
                b"assert __injected_review_execution__ == 'gate-captured-v1'\n"
                b"print('WINDOWS_JOB_INJECTED')\n"
            ),
        }
        snapshot = {
            "schemaVersion": 1, "status": "absent", "origin": None,
            "rawBase64": None, "rawSha256": None, "diagnostic": "absent",
        }
        observation = {
            "status": "not-requested", "repository": None,
            "diagnostic": "not-needed",
        }
        payload = json.dumps({
            "payloadVersion": 1,
            "sources": {
                name: base64.b64encode(value).decode("ascii")
                for name, value in source.items()
            },
            "review": {
                "schemaVersion": 1,
                "repositoryObservation": observation,
                "snapshot": snapshot,
                "snapshotId": snapshot_id,
            },
        }, sort_keys=True, separators=(",", ":")).encode("ascii")
        result = subprocess.run(
            [sys.executable, "-I", "-c", module._SCAN_BOOTSTRAP,
             "--gate-git-executable", sys.executable],
            input=payload,
            capture_output=True,
            timeout=10.0,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        self.assertEqual(result.stdout.strip(), b"WINDOWS_JOB_INJECTED")

    def test_frozen_bootstrap_injects_held_posix_helper_and_reaches_range_main(
        self,
    ) -> None:
        git_executable = shutil.which("git")
        if git_executable is None:
            self.skipTest("git is required")
        module = self._module("posix_helper_bootstrap")
        fds, closure = module._capture_source_closure()
        captured_modules = None
        try:
            self.assertEqual(
                tuple(node.role for node in closure.nodes),
                module.SOURCE_ROLE_ORDER,
            )
            captured_modules = module._load_captured_review_modules(closure)
            snapshot = {
                "schemaVersion": 1, "status": "absent", "origin": None,
                "rawBase64": None, "rawSha256": None, "diagnostic": "absent",
            }
            observation = {
                "status": "not-requested", "repository": None,
                "diagnostic": "not-needed",
            }
            review = {
                "schemaVersion": 1,
                "repositoryObservation": observation,
                "snapshot": snapshot,
                "snapshotId": captured_modules.policy_module.H(
                    "orchestrarium.publication-review.snapshot.v1", snapshot
                ),
            }
            payload = module._closure_payload(
                closure, review, captured_modules.policy_module.C
            )
            with temporary_repository_workdir() as repository_workdir:
                result = subprocess.run(
                    [
                        sys.executable,
                        "-I",
                        "-c",
                        module._SCAN_BOOTSTRAP,
                        "--gate-git-executable",
                        git_executable,
                        "--range",
                        "origin",
                        "main",
                    ],
                    cwd=repository_workdir,
                    input=payload,
                    capture_output=True,
                    timeout=10.0,
                )
        finally:
            if captured_modules is not None:
                module._release_captured_review_modules(captured_modules)
            for fd in fds:
                os.close(fd)

        combined = result.stdout + result.stderr
        self.assertEqual(2, result.returncode, combined.decode("utf-8", "replace"))
        self.assertIn(b"id=PS-MSG-RANGE", result.stderr)
        self.assertNotIn(b"helper unavailable", combined)

    def _pending(self, module, binding, argv):
        interpreter = module._interpreter_identity()
        payload = b""
        captured_review = module.CapturedReviewPayload(
            module.CapturedReviewModules(object(), object(), ()),
            {}, "a" * 64,
            {"status": "not-requested", "repository": None, "diagnostic": "not-needed"},
            None, False, payload, hashlib.sha256(payload).hexdigest(),
        )
        return module.PendingScanInvocation(
            "invocation", "attempt", binding, self._closure(module),
            interpreter, tuple(argv), object(), captured_review,
        )

    def test_r3_worker_start_failure_reaps_every_partial_start(self) -> None:
        module = self._module("worker_start")
        binding = module.PushScanBinding(
            "generic", "origin", "refs/heads/main", "1" * 40, "1" * 40
        )
        real_popen = module.subprocess.Popen
        real_start = module.threading.Thread.start

        for fail_after in range(3):
            children = []
            started = []
            starts = 0

            def capture_popen(*args, **kwargs):
                process = real_popen(*args, **kwargs)
                children.append(process)
                return process

            def guarded_start(worker):
                nonlocal starts
                ordinal = starts
                starts += 1
                if ordinal == fail_after:
                    raise RuntimeError("synthetic-worker-start")
                real_start(worker)
                started.append(worker)

            caught = None
            alive_before_test_cleanup = None
            live_workers_before_test_cleanup = None
            try:
                with mock.patch.object(module.subprocess, "Popen", side_effect=capture_popen), \
                     mock.patch.object(module.threading.Thread, "start", new=guarded_start):
                    try:
                        pending = self._pending(
                            module, binding,
                            (sys.executable, "-u", "-c", "import time; time.sleep(60)"),
                        )
                        module._run_snapshot_child(
                            pending, b"", str(REPO_ROOT.resolve())
                        )
                    except Exception as exc:
                        caught = exc
                self.assertEqual(len(children), 1)
                alive_before_test_cleanup = children[0].poll() is None
                live_workers_before_test_cleanup = any(worker.is_alive() for worker in started)
            finally:
                for child in children:
                    if child.poll() is None:
                        child.kill()
                    child.wait(timeout=2)
                for worker in started:
                    worker.join(timeout=2)
            with self.subTest(fail_after=fail_after):
                self.assertIsInstance(caught, module.PrRouteDenied)
                self.assertEqual(caught.failure_id, "PGG-SCAN-EXECUTION")
                self.assertFalse(alive_before_test_cleanup, "R3-WORKER-START-CHILD-LIVE")
                self.assertFalse(live_workers_before_test_cleanup, "R3-WORKER-START-WORKER-LIVE")

    def test_r3_pending_result_correlation_denies_before_parse(self) -> None:
        module = self._module("pending_correlation")
        fixtures = TestPublicationReviewedExceptionGateR2()
        policy = fixtures._policy_module()
        snapshot, snapshot_id = fixtures._synthetic_snapshot(policy)
        repository = fixtures._synthetic_repository()
        used_list, used_token, applied_set, repository_sha256 = (
            fixtures._review_wire_fields(policy, repository)
        )
        payload_bytes = policy.C({"syntheticSwappedPendingFixture": 1})
        captured_modules = module.CapturedReviewModules(policy, object(), ())
        captured_review = module.CapturedReviewPayload(
            captured_modules,
            snapshot,
            snapshot_id,
            {"status": "captured", "repository": repository, "diagnostic": "none"},
            repository, True, payload_bytes,
            hashlib.sha256(payload_bytes).hexdigest(),
        )
        qualified = fixtures._qualified_range_line(
            snapshot_id, used_token, applied_set
        ).encode("ascii")
        finalization = {
            "inputSnapshotId": snapshot_id,
            "usedList": used_list,
            "currentSnapshotId": snapshot_id,
            "repositorySha256": repository_sha256,
            "status": "valid",
            "reason": "none",
            "resourcesSettled": True,
        }
        binding = module.PushScanBinding(
            "generic", "origin", "refs/heads/main", "1" * 40, "1" * 40
        )
        interpreter_id = module.TrustedInterpreterIdentity(str(Path(sys.executable).resolve()), ())
        closure = dataclasses.replace(
            self._closure(module), interpreter_identity=interpreter_id
        )
        fd = os.open(os.devnull, os.O_RDONLY)
        repository_workdir = str(REPO_ROOT.resolve())
        git_exe = str(Path(shutil.which("git") or "").resolve(strict=True))
        original_pending = []

        def swapped_result(pending, _payload, _repository_workdir):
            original_pending.append(pending)
            settled = TestPublicationSafetyTrustedScanR5Proof()._pending_fixture(
                module, "generic", captured_review=pending.captured_review
            )
            pending.child_identity = settled["pending"].child_identity
            pending.supervisor = settled["pending"].supervisor
            pending.settlement = settled["pending"].settlement
            pending.state = settled["pending"].state
            wrong = module.PendingScanInvocation(
                "swapped", pending.attempt_id, pending.binding, pending.closure,
                pending.interpreter_identity, pending.exact_argv, object(),
                pending.captured_review,
            )
            launched = module.LaunchedScanInvocation(
                wrong, 999, object(), wrong.invocation_id, wrong.attempt_id,
                wrong.binding, wrong.exact_argv, wrong.result_slot,
            )
            execution = module.TrustedExecutionRecord(
                wrong, launched, wrong.result_slot, True, 0, qualified, b"",
                None, closure, interpreter_id, "trusted",
            )
            return launched, (execution,)

        with mock.patch.object(
            module, "_capture_source_closure", return_value=((fd,), closure)
        ), mock.patch.object(
            module, "_load_captured_review_modules", return_value=captured_modules
        ), mock.patch.object(
            module, "_capture_review_payload", return_value=captured_review
        ), mock.patch.object(
            module, "_interpreter_identity", return_value=interpreter_id
        ), mock.patch.object(
            module, "_recheck_source_closure", return_value=closure
        ), mock.patch.object(
            module, "_run_snapshot_child", side_effect=swapped_result
        ), mock.patch.object(
            module, "_refresh_scan_binding", return_value=binding
        ), mock.patch.object(
            module, "parse_publication_safety_observation",
            wraps=module.parse_publication_safety_observation,
        ) as parser, mock.patch.object(
            module, "_verify_used_review_currentness",
            return_value=(finalization, used_list),
        ) as finalizer:
            with self.assertRaises(module.PrRouteDenied) as caught:
                module._run_authoritative_scan(binding, repository_workdir, git_exe)
        self.assertEqual(caught.exception.failure_id, "PGG-SCAN-CORRELATION")
        parser.assert_not_called()
        finalizer.assert_not_called()
        self.assertEqual(original_pending[0].state, module.PendingState.FAILED)
        self.assertIsNone(original_pending[0].consumption_id)

        original = module.PendingScanInvocation(
            "invocation", "attempt", binding, closure, interpreter_id,
            ("python", "-I"), object(),
        )
        self.assertEqual(original.state, module.PendingState.PREPARED)
        self.assertFalse(hasattr(original, "_replace"))

    def test_r3_complete_executable_closure_rejects_dynamic_classifier(self) -> None:
        module = self._module("closure")
        self.assertTrue(hasattr(module, "CanonicalSourceClosure"), "R3-CLOSURE-TYPE")
        self.assertTrue(hasattr(module, "SourceNode"), "R3-CLOSURE-NODE")
        self.assertTrue(hasattr(module, "_capture_source_closure"), "R3-CLOSURE-OWNER")
        scanner_source = (
            REPO_ROOT / "scripts" / "universal-hooks" / "scripts" /
            "check-publication-safety.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("def _load_path_finder", scanner_source, "R3-DYNAMIC-CLASSIFIER")
        self.assertIn(
            "__injected_posix_process_group_module__",
            scanner_source,
            "R3-HELD-POSIX-HELPER",
        )
        source_paths = {
            "gate": CANONICAL_HOOK,
            "hook_common": CANONICAL_HOOK.with_name("hook_common.py"),
            "classifier": (
                REPO_ROOT / "scripts" / "universal-hooks" / "hooks" /
                "check-machine-local-path.py"
            ),
            "posix_helper": (
                REPO_ROOT / "scripts" / "process_supervision" /
                "posix_process_group.py"
            ),
            "windows_job": (
                REPO_ROOT / "scripts" / "process_supervision" / "windows_job.py"
            ),
            "scanner": CANONICAL_HOOK.with_name("check-publication-safety.py"),
            "publication_review_policy": CANONICAL_HOOK.with_name(
                "publication_review_policy.py"
            ),
            "linked_runtime_subroots": REPO_ROOT / "scripts" / "linked_runtime_subroots.py",
        }
        sources = {role: path.read_bytes() for role, path in source_paths.items()}
        original_file = module.__file__
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            try:
                for layout in module.SOURCE_LAYOUTS:
                    suffix_gate = root / layout.name / Path(*layout.gate_suffix)
                    trust_root = suffix_gate.parent
                    for _index in range(layout.trust_root_up):
                        trust_root = trust_root.parent
                    role_paths = {
                        role: trust_root / relative
                        for role, relative in layout.role_paths
                    }
                    for role, target in role_paths.items():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(sources[role])
                    gate = role_paths["gate"]
                    module.__file__ = str(gate)
                    fds, closure = module._capture_source_closure()
                    try:
                        with self.subTest(layout=layout.name, phase="roles"):
                            self.assertEqual(
                                tuple(node.role for node in closure.nodes),
                                module.SOURCE_ROLE_ORDER,
                            )
                        self.assertEqual(
                            len(fds), len(closure.components) + len(closure.nodes) + 1,
                            "R4-CLOSURE-HELD-HANDLE-CARDINALITY",
                        )
                        layout_row, trust_root = module._layout_for_gate(gate)
                        self.assertEqual(layout_row, closure.layout)
                        root_stat = trust_root.stat()
                        os.utime(
                            trust_root,
                            ns=(root_stat.st_atime_ns, root_stat.st_mtime_ns + 1_000_000),
                        )
                        with self.subTest(layout=layout.name, phase="component"):
                            with self.assertRaises(ValueError):
                                module._recheck_source_closure(fds, closure)
                    finally:
                        for fd in fds:
                            os.close(fd)

                    for role, target in role_paths.items():
                        role_source = sources[role]
                        target.write_bytes(role_source)
                        fds, closure = module._capture_source_closure()
                        try:
                            try:
                                target.write_bytes(role_source + b"\n# mutation\n")
                            except PermissionError:
                                mutation_blocked = True
                            else:
                                mutation_blocked = False
                            with self.subTest(
                                layout=layout.name, phase="node", role=role
                            ):
                                if mutation_blocked:
                                    self.assertEqual(os.name, "nt")
                                else:
                                    with self.assertRaises(ValueError):
                                        module._recheck_source_closure(fds, closure)
                        finally:
                            for fd in fds:
                                os.close(fd)
                            target.write_bytes(role_source)

                    fds, closure = module._capture_source_closure()
                    try:
                        with mock.patch.object(
                            module, "_SCAN_BOOTSTRAP", module._SCAN_BOOTSTRAP + "\n# mutation"
                        ), self.assertRaises(ValueError):
                            module._recheck_source_closure(fds, closure)
                        changed_interpreter = module.InterpreterIdentity(
                            closure.interpreter_identity.absolute_resolved_path,
                            closure.interpreter_identity.file_identity + (99,),
                        )
                        with mock.patch.object(
                            module, "_interpreter_identity", return_value=changed_interpreter
                        ), self.assertRaises(ValueError):
                            module._recheck_source_closure(fds, closure)
                    finally:
                        for fd in fds:
                            os.close(fd)
            finally:
                module.__file__ = original_file

    def test_r3_all_channel_redaction_matrix(self) -> None:
        module = self._module("redaction")
        sentinels = {
            "rejected-producer": "SENTINEL_REJECTED_PRODUCER",
            "remote": "SENTINEL_REMOTE",
            "destination": "SENTINEL_DESTINATION",
            "command": "SENTINEL_COMMAND",
            "child-stdout": "SENTINEL_CHILD_STDOUT",
            "child-stderr": "SENTINEL_CHILD_STDERR",
            "transcript": "SENTINEL_TRANSCRIPT_OUTPUT",
            "assertion": "SENTINEL_ASSERTION_TEXT",
            "evidence": "SENTINEL_EVIDENCE_TEXT",
        }
        for route in ("generic", "strict"):
            failure_id = "PGG-SCAN-EXECUTION" if route == "generic" else "PRG-SCAN-EXECUTION"
            rendered = module.SCAN_DENIAL_REASONS[failure_id]
            for channel, sentinel in sentinels.items():
                with self.subTest(route=route, channel=channel, boundary="formatter"):
                    self.assertNotIn(sentinel, rendered, "R3-REDACTION-CHANNEL")

                stdout = io.StringIO()
                with mock.patch.object(
                    module,
                    "build_preflight_from_stdin",
                    return_value=_heavy_preflight(module),
                ), mock.patch.object(
                    module, "evaluate_heavy",
                    side_effect=module.PrRouteDenied(sentinel),
                ), contextlib.redirect_stdout(stdout):
                    self.assertEqual(module.main(), 0)
                with self.subTest(route=route, channel=channel, boundary="runtime"):
                    self.assertNotIn(sentinel, stdout.getvalue(), "R3-REDACTION-RUNTIME")


class TestPublicationSafetyTrustedScanR4(unittest.TestCase):
    """R4 guards for total settlement, one-use correlation, closure, and truth."""

    def _module(self, suffix: str):
        return _load_gate_module(CANONICAL_HOOK, "publication_r4_" + suffix)

    def test_r4_supervisor_wait_error_cannot_escape_later_cleanup(self) -> None:
        module = self._module("supervisor")

        class Stream:
            def __init__(self):
                self.closed = False
            def close(self):
                self.closed = True

        class Process:
            def __init__(self):
                self.pid = 41
                self.returncode = None
                self.stdin, self.stdout, self.stderr = Stream(), Stream(), Stream()
                self.wait_calls = 0
                self.killed = False
            def poll(self):
                return self.returncode
            def terminate(self):
                return None
            def wait(self, timeout=None):
                self.wait_calls += 1
                if self.wait_calls == 1:
                    raise OSError("synthetic-wait")
                self.returncode = -9
                return self.returncode
            def kill(self):
                self.killed = True

        process = Process()
        supervisor = module.ChildSupervisor(process, attempt_seconds=0.05)
        settlement = supervisor.settle()
        if not settlement.complete:
            settlement = supervisor.settle()
        self.assertTrue(process.killed, "R4-WAIT-ERROR-SKIPPED-KILL")
        self.assertTrue(all(stream.closed for stream in (process.stdin, process.stdout, process.stderr)))
        self.assertTrue(settlement.complete, "R4-SUPERVISOR-NOT-SETTLED")
        self.assertFalse(settlement.execution_eligible, "R4-CONTROL-ERROR-AUTHORIZED")
        self.assertLessEqual(settlement.certificate.attempts_used, 2)

        class ChaosStream:
            def __init__(self, name, fault):
                self.name, self.fault, self.calls = name, fault, 0
                self.closed = False
            def close(self):
                self.calls += 1
                if self.fault == self.name:
                    raise KeyboardInterrupt("synthetic-" + self.name)
                self.closed = True

        class ChaosWorker:
            def __init__(self, fault):
                self.fault, self.join_calls, self.observe_calls = fault, 0, 0
            def join(self, timeout=None):
                self.join_calls += 1
                if self.fault == "worker-join":
                    raise KeyboardInterrupt("synthetic-worker-join")
            def is_alive(self):
                self.observe_calls += 1
                if self.fault == "worker-observe":
                    raise KeyboardInterrupt("synthetic-worker-observe")
                if self.fault == "worker-join":
                    return self.observe_calls == 1
                return False

        class ChaosProcess:
            def __init__(self, fault):
                self.pid, self.returncode, self.fault = 71, None, fault
                self.stdin = ChaosStream("stdin-close", fault)
                self.stdout = ChaosStream("stdout-close", fault)
                self.stderr = ChaosStream("stderr-close", fault)
                self.poll_calls = self.terminate_calls = 0
                self.wait_calls = self.kill_calls = 0
            def poll(self):
                self.poll_calls += 1
                if self.fault == "poll" or (
                    self.fault == "final-poll" and self.poll_calls > 1
                ):
                    raise KeyboardInterrupt("synthetic-poll")
                return self.returncode
            def terminate(self):
                self.terminate_calls += 1
                if self.fault == "terminate":
                    raise KeyboardInterrupt("synthetic-terminate")
            def wait(self, timeout=None):
                self.wait_calls += 1
                if self.fault == "wait" or (
                    self.fault == "wait-first" and self.wait_calls == 1
                ) or (
                    self.fault == "kill" and self.wait_calls == 1
                ):
                    raise KeyboardInterrupt("synthetic-wait")
                self.returncode = -9
                return self.returncode
            def kill(self):
                self.kill_calls += 1
                if self.fault == "kill":
                    raise KeyboardInterrupt("synthetic-kill")

        chaos_rows = (
            "poll", "stdin-close", "terminate", "wait-first", "wait", "kill",
            "stdout-close", "stderr-close", "worker-join", "worker-observe",
            "final-poll",
        )
        for fault in chaos_rows:
            process = ChaosProcess(fault)
            worker = ChaosWorker(fault)
            supervisor = module.ChildSupervisor(process, attempt_seconds=0.01)
            supervisor.workers.append(module._OwnedWorker(worker, "started"))
            first = supervisor.settle()
            final = first if first.complete else supervisor.settle()
            with self.subTest(fault=fault):
                self.assertGreaterEqual(process.poll_calls, 1)
                self.assertEqual(worker.join_calls, int(fault == "worker-join"))
                self.assertGreaterEqual(worker.observe_calls, 1)
                self.assertIsNotNone(final.certificate)
                self.assertLessEqual(final.certificate.attempts_used, 2)
                self.assertIn(
                    "wait" if fault == "wait-first" else fault,
                    final.certificate.operation_errors,
                )
                self.assertFalse(final.execution_eligible)
                if fault in {"wait", "worker-observe"}:
                    self.assertEqual(process.stdin.calls, 0)
                    self.assertEqual(process.stdout.calls, 0)
                    self.assertEqual(process.stderr.calls, 0)
                    self.assertFalse(process.stdin.closed)
                    self.assertFalse(process.stdout.closed)
                    self.assertFalse(process.stderr.closed)
                    self.assertFalse(final.complete)
                elif fault in {"stdin-close", "stdout-close", "stderr-close"}:
                    for stream in (process.stdin, process.stdout, process.stderr):
                        if stream.name == fault:
                            self.assertGreaterEqual(stream.calls, 1)
                            self.assertFalse(stream.closed)
                        else:
                            self.assertTrue(stream.closed)
                    self.assertFalse(final.complete)
                else:
                    self.assertTrue(process.stdin.closed)
                    self.assertTrue(process.stdout.closed)
                    self.assertTrue(process.stderr.closed)

    def test_r4_pending_owner_is_mutable_locked_noncopyable_and_one_use(self) -> None:
        module = self._module("pending")
        self.assertFalse(issubclass(module.PendingScanInvocation, tuple), "R4-PENDING-STILL-TUPLE")
        self.assertTrue(hasattr(module.PendingScanInvocation, "correlate_and_consume_once"))

        def fixture(route):
            binding = module.PushScanBinding(
                route, "origin", "refs/heads/main", "1" * 40, "1" * 40
            )
            interpreter = module._interpreter_identity()
            root = module.PathComponentIdentity(".", "directory", (1,))
            closure = module.CanonicalSourceClosure(
                module.SOURCE_LAYOUTS[0], root, (root,), (), "a" * 64,
                (2,), "b" * 64, interpreter,
                module.RootLocatorIdentity("gate.py", ".", "directory", (1,), None, ".", (1,), "gate.py", (2,)),
            )
            pending = module.PendingScanInvocation(
                "invocation", "attempt", binding, closure, interpreter,
                ("python", "-I"), object(), created_tick=time.monotonic(),
                authorization_deadline=time.monotonic() + 10,
            )

            class Process:
                pid = 41

            supervisor = module.ChildSupervisor(Process(), attempt_seconds=0.01)
            tick = time.monotonic()
            streams = tuple(
                module.GateTransportObservation(name, "owned", True, None, tick)
                for name in ("stdin", "stdout", "stderr")
            )
            certificate = module.GateSettlementCertificate(
                supervisor.supervisor_id, 41, 0, streams, (), (), 1, tick + 1e-6
            )
            settlement = module.GateSettlement(
                module.GateSettlementState.SETTLED, certificate, True
            )
            pending.child_identity = 41
            pending.supervisor = supervisor
            pending.settlement = settlement
            pending.state = module.PendingState.SETTLED
            launched = module.LaunchedScanInvocation(
                pending, 41, supervisor, pending.invocation_id,
                pending.attempt_id, binding, pending.exact_argv,
                pending.result_slot,
            )
            receipt = range_receipt_v3(
                files=0,
                remote=binding.remote,
                dst=binding.destination,
                tip=binding.source_oid,
            ).encode("ascii")
            record = module.TrustedExecutionRecord(
                pending, launched, pending.result_slot, True, 0, receipt, b"",
                settlement, closure, interpreter, "trusted",
            )
            return {
                "pending": pending, "binding": binding, "closure": closure,
                "interpreter": interpreter, "supervisor": supervisor,
                "certificate": certificate, "settlement": settlement,
                "launched": launched, "record": record,
                "freshness": certificate.verified_at_monotonic_tick + 1e-4,
            }

        for route in ("generic", "strict"):
            row = fixture(route)
            pending = row["pending"]
            with mock.patch.object(
                module, "parse_publication_safety_observation",
                wraps=module.parse_publication_safety_observation,
            ) as parser:
                evidence = pending.correlate_and_consume_once(
                    row["launched"], (row["record"],), row["closure"],
                    row["interpreter"], row["binding"], row["freshness"],
                )
                self.assertIsInstance(evidence, module.ConsumedAuthoritativeEvidence)
                self.assertEqual(pending.state, module.PendingState.CONSUMED)
                with self.assertRaises(module.PrRouteDenied) as replay:
                    pending.correlate_and_consume_once(
                        row["launched"], (row["record"],), row["closure"],
                        row["interpreter"], row["binding"], row["freshness"],
                    )
                self.assertEqual(
                    replay.exception.failure_id,
                    "PGG-RECEIPT-USED" if route == "generic" else "PRG-RECEIPT-USED",
                )
                self.assertEqual(parser.call_count, 1, "R4-REPLAY-PARSED")

        mutations = {
            "wrong-pending": lambda row: row.update(launched=row["launched"]._replace(pending=object())),
            "wrong-invocation": lambda row: row.update(launched=row["launched"]._replace(invocation_id="wrong")),
            "wrong-attempt": lambda row: row.update(launched=row["launched"]._replace(attempt_id="wrong")),
            "wrong-argv": lambda row: row.update(launched=row["launched"]._replace(exact_argv=("wrong",))),
            "wrong-launch-slot": lambda row: row.update(launched=row["launched"]._replace(result_slot=object())),
            "wrong-record-slot": lambda row: row.update(record=dataclasses.replace(row["record"], result_slot=object())),
            "wrong-child": lambda row: row.update(launched=row["launched"]._replace(child_handle=99)),
            "wrong-record-launch": lambda row: row.update(record=dataclasses.replace(row["record"], launched=object())),
            "wrong-settlement": lambda row: row.update(record=dataclasses.replace(
                row["record"], settlement=module.GateSettlement(
                    module.GateSettlementState.SETTLED, row["certificate"], True
                )
            )),
            "wrong-closure": lambda row: row.update(closure=dataclasses.replace(row["closure"], digest="d" * 64)),
            "wrong-record-closure": lambda row: row.update(record=dataclasses.replace(
                row["record"], closure_after=dataclasses.replace(row["closure"], digest="d" * 64)
            )),
            "wrong-interpreter": lambda row: row.update(interpreter=module.InterpreterIdentity("wrong", ())),
            "wrong-record-interpreter": lambda row: row.update(record=dataclasses.replace(
                row["record"], interpreter_identity_after=module.InterpreterIdentity("wrong", ())
            )),
            "wrong-binding": lambda row: row.update(binding=row["binding"]._replace(destination="other")),
            "stale-tick": lambda row: row.update(freshness=row["certificate"].verified_at_monotonic_tick),
            "wrong-state": lambda row: setattr(row["pending"], "state", module.PendingState.PREPARED),
            "stale-deadline": lambda row: object.__setattr__(row["pending"], "authorization_deadline", 0.0),
            "empty-records": lambda row: row.update(records=()),
            "duplicate-records": lambda row: row.update(records=(row["record"], row["record"])),
        }
        for route in ("generic", "strict"):
            for mutation, apply_mutation in mutations.items():
                row = fixture(route)
                apply_mutation(row)
                if "records" not in row:
                    row["records"] = (row["record"],)
                with self.subTest(route=route, mutation=mutation):
                    with mock.patch.object(
                        module, "parse_publication_safety_observation",
                        wraps=module.parse_publication_safety_observation,
                    ) as parser, self.assertRaises(module.PrRouteDenied):
                        row["pending"].correlate_and_consume_once(
                            row["launched"], row["records"], row["closure"],
                            row["interpreter"], row["binding"], row["freshness"],
                        )
                    parser.assert_not_called()

        pending = fixture("generic")["pending"]
        self.assertFalse(hasattr(pending, "_replace"), "R4-PENDING-COPY-SURFACE")
        with self.assertRaises(TypeError):
            __import__("copy").copy(pending)
        for field_name in (
            "invocation_id", "attempt_id", "binding", "closure",
            "interpreter_identity", "exact_argv", "result_slot",
            "captured_review",
            "created_tick", "authorization_deadline",
        ):
            with self.subTest(identity_field=field_name), self.assertRaises(AttributeError):
                setattr(pending, field_name, getattr(pending, field_name))

    def test_r4_closure_declares_four_layouts_and_complete_components(self) -> None:
        module = self._module("closure")
        self.assertEqual(len(module.SOURCE_LAYOUTS), 4, "R4-TOPOLOGY-CARDINALITY")
        self.assertEqual(
            {layout.name for layout in module.SOURCE_LAYOUTS},
            {"universal", "codex-source", "claude-source", "component"},
        )
        self.assertIn("bootstrap_digest", {field.name for field in dataclasses.fields(module.CanonicalSourceClosure)})
        self.assertIn("components", {field.name for field in dataclasses.fields(module.CanonicalSourceClosure)})
        self.assertIn("interpreter_identity", {field.name for field in dataclasses.fields(module.CanonicalSourceClosure)})

    def test_r4_publication_authority_semantic_residue_is_zero(self) -> None:
        live_files = (
            CANONICAL_HOOK,
            *HOOKS,
            REPO_ROOT / "RELEASE_NOTES.md",
        )
        imperative = re.compile(
            r"\b(?:run|rerun|provide|paste|trust|rely\s+on)\b[^.\n]{0,48}"
            r"\b(?:manual|standalone|final|tracked|path|range|publication-safety)[- ]*scan\b",
            re.IGNORECASE,
        )
        hits = []
        for path in live_files:
            lines = path.read_text(encoding="utf-8").splitlines()
            if path.name == "RELEASE_NOTES.md":
                lines = lines[12:24]
            for line_number, line in enumerate(lines, 1):
                if imperative.search(line):
                    hits.append((path.name, line_number))
        self.assertEqual(hits, [], "R4-SEMANTIC-SCAN-REMEDIATION")

class TestPublicationSafetyTrustedScanR5Proof(unittest.TestCase):
    """Proof-only inventory for the four architecture R4 enforcement gaps."""


    def _module(self, suffix: str):
        return _load_gate_module(CANONICAL_HOOK, "publication_r5_" + suffix)

    def _pending_fixture(
        self, module, route: str, *, remote: str = "origin",
        destination: str = "refs/heads/main",
        captured_review=None, head_oid: str | None = None,
    ) -> dict[str, object]:
        binding = module.PushScanBinding(
            route, remote, destination, "1" * 40, head_oid or "1" * 40
        )
        interpreter = module._interpreter_identity()
        root = module.PathComponentIdentity(".", "directory", (1,))
        node = module.SourceNode(
            "gate", "gate.py", (2,), 1, len(b"gate"),
            hashlib.sha256(b"gate").hexdigest(), b"gate",
        )
        closure = module.CanonicalSourceClosure(
            module.SOURCE_LAYOUTS[0], root, (root,), (node,), "a" * 64,
            (2,), "b" * 64, interpreter,
            module.RootLocatorIdentity("gate.py", ".", "directory", (1,), None, ".", (1,), "gate.py", (2,)),
        )
        pending = module.PendingScanInvocation(
            "invocation", "attempt", binding, closure, interpreter,
            ("python", "-I"), object(), captured_review,
            created_tick=time.monotonic(),
            authorization_deadline=time.monotonic() + 10,
        )

        class Process:
            pid = 41

        supervisor = module.ChildSupervisor(Process(), attempt_seconds=0.01)
        tick = time.monotonic()
        streams = tuple(
            module.GateTransportObservation(name, "owned", True, None, tick)
            for name in ("stdin", "stdout", "stderr")
        )
        workers = (module.GateWorkerObservation(7, "started", "joined", tick),)
        certificate = module.GateSettlementCertificate(
            supervisor.supervisor_id, 41, 0, streams, workers, (), 1,
            tick + 1e-6,
        )
        settlement = module.GateSettlement(
            module.GateSettlementState.SETTLED, certificate, True
        )
        pending.child_identity = 41
        pending.supervisor = supervisor
        pending.settlement = settlement
        pending.state = module.PendingState.SETTLED
        launched = module.LaunchedScanInvocation(
            pending, 41, supervisor, pending.invocation_id,
            pending.attempt_id, binding, pending.exact_argv,
            pending.result_slot,
        )
        receipt = range_receipt_v3(
            files=0,
            remote=remote,
            dst=destination,
            tip=binding.source_oid,
        ).encode("ascii")
        record = module.TrustedExecutionRecord(
            pending, launched, pending.result_slot, True, 0, receipt, b"",
            settlement, closure, interpreter, "trusted",
        )
        return {
            "pending": pending,
            "binding": binding,
            "closure": closure,
            "interpreter": interpreter,
            "supervisor": supervisor,
            "certificate": certificate,
            "settlement": settlement,
            "launched": launched,
            "record": record,
            "records": (record,),
            "freshness": certificate.verified_at_monotonic_tick + 1e-4,
        }

    def test_generic_explicit_source_keeps_current_head_and_receipt_fences(self) -> None:
        module = self._module("explicit_source_current_head")
        def consume(data, *, record=None, binding=None):
            return data["pending"].correlate_and_consume_once(data["launched"],
                (record or data["record"],), data["closure"], data["interpreter"],
                binding or data["binding"], data["freshness"])
        valid = self._pending_fixture(module, "generic", head_oid="2" * 40)
        consumed = consume(valid)
        self.assertTrue(consumed.consumption_id)
        with self.assertRaises(module.PrRouteDenied) as reused:
            consume(valid)
        self.assertEqual(reused.exception.failure_id, "PGG-RECEIPT-USED")
        for defect in ("current-head-drift", "changed-ref", "old-invocation-receipt", "strict-pr-policy"):
            data = self._pending_fixture(module, "pr" if defect == "strict-pr-policy" else "generic", head_oid="2" * 40)
            record = data["record"]
            binding = data["binding"]
            if defect == "current-head-drift":
                binding = binding._replace(head_oid="3" * 40)
            elif defect == "changed-ref":
                record = dataclasses.replace(record, stdout=range_receipt_v3(dst="refs/heads/unapproved", tip="1" * 40).encode("ascii"))
            elif defect == "old-invocation-receipt":
                record = valid["record"]
            with self.subTest(defect=defect), self.assertRaises(module.PrRouteDenied):
                consume(data, record=record, binding=binding)

    def test_r5_gate_certificate_retry_and_pending_participant_matrix(self) -> None:
        module = self._module("certificate_pending")

        class Stream:
            def __init__(self):
                self.close_calls = 0
                self.closed = False
            def close(self):
                self.close_calls += 1
                self.closed = True

        class RetryProcess:
            def __init__(self):
                self.pid = 91
                self.returncode = None
                self.stdin, self.stdout, self.stderr = Stream(), Stream(), Stream()
                self.poll_calls = self.terminate_calls = self.kill_calls = 0
                self.wait_calls = 0
            def poll(self):
                self.poll_calls += 1
                if self.poll_calls >= 4:
                    self.returncode = 0
                return self.returncode
            def terminate(self):
                self.terminate_calls += 1
            def wait(self, timeout=None):
                self.wait_calls += 1
                raise TimeoutError("R5-BOUNDED-WAIT")
            def kill(self):
                self.kill_calls += 1

        process = RetryProcess()
        supervisor = module.ChildSupervisor(process, attempt_seconds=0.001)
        first = supervisor.settle()
        self.assertFalse(first.complete)
        self.assertIs(supervisor.process, process)
        second = supervisor.settle()
        self.assertTrue(second.complete)
        self.assertFalse(second.execution_eligible)
        self.assertEqual(second.certificate.attempts_used, 2)
        self.assertEqual(supervisor.child_identity, 91)
        actions = (
            process.poll_calls, process.terminate_calls, process.wait_calls,
            process.kill_calls,
            *(stream.close_calls for stream in (
                process.stdin, process.stdout, process.stderr
            )),
        )
        self.assertIs(supervisor.settle(), second)
        self.assertEqual(
            actions,
            (
                process.poll_calls, process.terminate_calls, process.wait_calls,
                process.kill_calls,
                *(stream.close_calls for stream in (
                    process.stdin, process.stdout, process.stderr
                )),
            ),
            "R5-SETTLED-REENTERED",
        )

        certificate = self._pending_fixture(module, "generic")["certificate"]
        certificate_mutations = {
            "return-code": dataclasses.replace(certificate, observed_return_code=None),
            "attempt-zero": dataclasses.replace(certificate, attempts_used=0),
            "attempt-overflow": dataclasses.replace(certificate, attempts_used=3),
            "stdin": dataclasses.replace(
                certificate,
                streams=(
                    dataclasses.replace(certificate.streams[0], closed_observed=False),
                    *certificate.streams[1:],
                ),
            ),
            "stdout": dataclasses.replace(
                certificate,
                streams=(
                    certificate.streams[0],
                    dataclasses.replace(certificate.streams[1], closed_observed=False),
                    certificate.streams[2],
                ),
            ),
            "stderr": dataclasses.replace(
                certificate,
                streams=(
                    *certificate.streams[:2],
                    dataclasses.replace(certificate.streams[2], closed_observed=False),
                ),
            ),
            "worker": dataclasses.replace(
                certificate,
                workers=(dataclasses.replace(certificate.workers[0], terminal="live"),),
            ),
            "verification-order": dataclasses.replace(
                certificate,
                verified_at_monotonic_tick=max(
                    row.observed_at_monotonic_tick
                    for row in certificate.streams + certificate.workers
                ),
            ),
        }
        for name, mutated in certificate_mutations.items():
            with self.subTest(certificate=name):
                self.assertFalse(mutated.complete, "R5-GATE-CERTIFICATE-ACCEPTED")

        def replace_settlement(row, certificate=None, *, eligible=True, state=None):
            replacement = module.GateSettlement(
                state or module.GateSettlementState.SETTLED,
                certificate or row["certificate"],
                eligible,
            )
            row["pending"].settlement = replacement
            row["settlement"] = replacement
            row["record"] = dataclasses.replace(
                row["record"], settlement=replacement
            )
            row["records"] = (row["record"],)

        mutations = {
            "launch-pending": lambda row: row.update(
                launched=row["launched"]._replace(pending=object())
            ),
            "record-pending": lambda row: row.update(
                record=dataclasses.replace(row["record"], pending=object())
            ),
            "launch-supervisor": lambda row: row.update(
                launched=row["launched"]._replace(supervisor_token=object())
            ),
            "pending-supervisor": lambda row: setattr(
                row["pending"], "supervisor", object()
            ),
            "pending-child": lambda row: setattr(row["pending"], "child_identity", 99),
            "launch-child": lambda row: row.update(
                launched=row["launched"]._replace(child_handle=99)
            ),
            "process-child": lambda row: setattr(row["supervisor"].process, "pid", 99),
            "supervisor-child": lambda row: setattr(row["supervisor"], "child_identity", 99),
            "certificate-supervisor": lambda row: replace_settlement(
                row,
                dataclasses.replace(row["certificate"], supervisor_id="other"),
            ),
            "certificate-child": lambda row: replace_settlement(
                row,
                dataclasses.replace(row["certificate"], child_identity=99),
            ),
            "certificate-return": lambda row: replace_settlement(
                row,
                dataclasses.replace(row["certificate"], observed_return_code=None),
            ),
            "certificate-stream": lambda row: replace_settlement(
                row,
                dataclasses.replace(
                    row["certificate"],
                    streams=(
                        dataclasses.replace(
                            row["certificate"].streams[0], closed_observed=False
                        ),
                        *row["certificate"].streams[1:],
                    ),
                ),
            ),
            "certificate-worker": lambda row: replace_settlement(
                row,
                dataclasses.replace(
                    row["certificate"],
                    workers=(dataclasses.replace(
                        row["certificate"].workers[0], terminal="live"
                    ),),
                ),
            ),
            "settlement-state": lambda row: replace_settlement(
                row, state=module.GateSettlementState.FAILED_UNSETTLED
            ),
            "settlement-eligible": lambda row: replace_settlement(row, eligible=False),
            "record-settlement": lambda row: row.update(
                record=dataclasses.replace(
                    row["record"],
                    settlement=module.GateSettlement(
                        module.GateSettlementState.SETTLED,
                        row["certificate"], True,
                    ),
                )
            ),
            "launch-invocation": lambda row: row.update(
                launched=row["launched"]._replace(invocation_id="other")
            ),
            "launch-attempt": lambda row: row.update(
                launched=row["launched"]._replace(attempt_id="other")
            ),
            "launch-binding": lambda row: row.update(
                launched=row["launched"]._replace(
                    binding=row["binding"]._replace(destination="other")
                )
            ),
            "launch-argv": lambda row: row.update(
                launched=row["launched"]._replace(exact_argv=("other",))
            ),
            "launch-slot": lambda row: row.update(
                launched=row["launched"]._replace(result_slot=object())
            ),
            "record-launch": lambda row: row.update(
                record=dataclasses.replace(row["record"], launched=object())
            ),
            "record-slot": lambda row: row.update(
                record=dataclasses.replace(row["record"], result_slot=object())
            ),
            "closure-freshness": lambda row: row.update(
                closure=dataclasses.replace(row["closure"], digest="d" * 64)
            ),
            "record-closure": lambda row: row.update(
                record=dataclasses.replace(
                    row["record"],
                    closure_after=dataclasses.replace(row["closure"], digest="d" * 64),
                )
            ),
            "interpreter-freshness": lambda row: row.update(
                interpreter=module.InterpreterIdentity("other", ())
            ),
            "record-interpreter": lambda row: row.update(
                record=dataclasses.replace(
                    row["record"],
                    interpreter_identity_after=module.InterpreterIdentity("other", ()),
                )
            ),
            "provenance": lambda row: row.update(
                record=dataclasses.replace(row["record"], provenance_verdict="other")
            ),
            "binding-freshness": lambda row: row.update(
                binding=row["binding"]._replace(destination="other")
            ),
            "freshness-order": lambda row: row.update(
                freshness=row["certificate"].verified_at_monotonic_tick
            ),
            "prepared-state": lambda row: setattr(
                row["pending"], "state", module.PendingState.PREPARED
            ),
            "correlated-state": lambda row: setattr(
                row["pending"], "state", module.PendingState.CORRELATED
            ),
            "failed-state": lambda row: setattr(
                row["pending"], "state", module.PendingState.FAILED
            ),
            "expired": lambda row: object.__setattr__(
                row["pending"], "authorization_deadline", 0.0
            ),
            "empty-records": lambda row: row.update(records=()),
            "duplicate-records": lambda row: row.update(
                records=(row["record"], row["record"])
            ),
            "unbounded": lambda row: row.update(
                record=dataclasses.replace(row["record"], bounded_completion=False)
            ),
        }
        for route in ("generic", "strict"):
            valid = self._pending_fixture(module, route)
            with mock.patch.object(
                module, "parse_publication_safety_observation",
                wraps=module.parse_publication_safety_observation,
            ) as parser:
                evidence = valid["pending"].correlate_and_consume_once(
                    valid["launched"], valid["records"], valid["closure"],
                    valid["interpreter"], valid["binding"], valid["freshness"],
                )
                self.assertIsInstance(evidence, module.ConsumedAuthoritativeEvidence)
                with self.assertRaises(module.PrRouteDenied):
                    valid["pending"].correlate_and_consume_once(
                        valid["launched"], valid["records"], valid["closure"],
                        valid["interpreter"], valid["binding"], valid["freshness"],
                    )
                self.assertEqual(parser.call_count, 1, "R5-REPLAY-PARSED")

            for name, mutate in mutations.items():
                row = self._pending_fixture(module, route)
                mutate(row)
                if name in {
                    "record-pending", "record-settlement", "record-launch",
                    "record-slot", "record-closure", "record-interpreter",
                    "provenance", "unbounded",
                }:
                    row["records"] = (row["record"],)
                with self.subTest(route=route, participant=name):
                    with mock.patch.object(
                        module, "parse_publication_safety_observation",
                        wraps=module.parse_publication_safety_observation,
                    ) as parser, self.assertRaises(module.PrRouteDenied):
                        row["pending"].correlate_and_consume_once(
                            row["launched"], row["records"], row["closure"],
                            row["interpreter"], row["binding"], row["freshness"],
                        )
                    parser.assert_not_called()

    def test_r5_four_layout_closure_and_actual_redaction_channels(self) -> None:
        module = self._module("closure_redaction")
        source_paths = {
            "gate": CANONICAL_HOOK,
            "hook_common": CANONICAL_HOOK.with_name("hook_common.py"),
            "classifier": (
                REPO_ROOT / "scripts" / "universal-hooks" / "hooks" /
                "check-machine-local-path.py"
            ),
            "posix_helper": (
                REPO_ROOT / "scripts" / "process_supervision" /
                "posix_process_group.py"
            ),
            "windows_job": (
                REPO_ROOT / "scripts" / "process_supervision" / "windows_job.py"
            ),
            "scanner": CANONICAL_HOOK.with_name("check-publication-safety.py"),
            "publication_review_policy": CANONICAL_HOOK.with_name(
                "publication_review_policy.py"
            ),
            "linked_runtime_subroots": REPO_ROOT / "scripts" / "linked_runtime_subroots.py",
        }
        sources = {role: path.read_bytes() for role, path in source_paths.items()}
        original_file = module.__file__
        scratch = REPO_ROOT / ".scratch"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="r5-closure-", dir=scratch) as td:
            root = Path(td)
            try:
                for layout_index, layout in enumerate(module.SOURCE_LAYOUTS):
                    suffix_gate = root / layout.name / Path(*layout.gate_suffix)
                    trust_root = suffix_gate.parent
                    for _index in range(layout.trust_root_up):
                        trust_root = trust_root.parent
                    paths = {
                        role: trust_root / relative
                        for role, relative in layout.role_paths
                    }
                    for role, path in paths.items():
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(sources[role])
                    module.__file__ = str(paths["gate"])
                    fds, closure = module._capture_source_closure()
                    try:
                        self.assertEqual(
                            tuple(node.role for node in closure.nodes),
                            module.SOURCE_ROLE_ORDER,
                        )
                        for index, component in enumerate(closure.components):
                            components = list(closure.components)
                            components[index] = dataclasses.replace(
                                component, identity=component.identity + (99,)
                            )
                            mutated = dataclasses.replace(
                                closure, components=tuple(components)
                            )
                            with self.subTest(
                                layout=layout.name,
                                participant="component",
                                name=component.root_relative_name,
                            ), self.assertRaises(ValueError):
                                module._recheck_source_closure(fds, mutated)

                        for index, node in enumerate(closure.nodes):
                            node_mutations = {
                                "identity": dataclasses.replace(
                                    node, file_identity=node.file_identity + (99,)
                                ),
                                "source": dataclasses.replace(
                                    node, source=node.source + b"\n"
                                ),
                                "digest": dataclasses.replace(node, sha256="0" * 64),
                                "path": dataclasses.replace(
                                    node, expected_path=str(root / "other.py")
                                ),
                            }
                            for field_name, changed_node in node_mutations.items():
                                nodes = list(closure.nodes)
                                nodes[index] = changed_node
                                mutated = dataclasses.replace(
                                    closure, nodes=tuple(nodes)
                                )
                                with self.subTest(
                                    layout=layout.name,
                                    participant=node.role,
                                    field=field_name,
                                ), self.assertRaises((ValueError, OSError)):
                                    module._recheck_source_closure(fds, mutated)

                        other_layout = module.SOURCE_LAYOUTS[
                            (layout_index + 1) % len(module.SOURCE_LAYOUTS)
                        ]
                        extras = {
                            "layout": dataclasses.replace(closure, layout=other_layout),
                            "component-cardinality": dataclasses.replace(
                                closure, components=closure.components[:-1]
                            ),
                            "node-cardinality": dataclasses.replace(
                                closure, nodes=closure.nodes[:-1]
                            ),
                            "bootstrap": dataclasses.replace(
                                closure, bootstrap_digest="0" * 64
                            ),
                            "interpreter": dataclasses.replace(
                                closure,
                                interpreter_identity=module.InterpreterIdentity(
                                    "other", closure.interpreter_identity.file_identity
                                ),
                            ),
                        }
                        for name, mutated in extras.items():
                            with self.subTest(
                                layout=layout.name, participant=name
                            ), self.assertRaises((ValueError, OSError)):
                                module._recheck_source_closure(fds, mutated)
                    finally:
                        for fd in fds:
                            os.close(fd)
            finally:
                module.__file__ = original_file

        child_out = "R5_CHILD_OUT_123456789"
        child_err = "R5_CHILD_ERR_123456789"
        producer_path = "R5_PRODUCER_PATH_123456789"
        remote = "R5_REMOTE_123456789"
        destination = "refs/heads/R5_DESTINATION_123456789"
        command_value = "R5_COMMAND_123456789"
        transcript_value = "R5_TRANSCRIPT_123456789"
        exception_value = "R5_EXCEPTION_123456789"
        boundary_rows: dict[str, tuple[BaseException, tuple[str, ...]]] = {}

        for channel, sentinel in (("child-stdout", child_out), ("child-stderr", child_err)):
            row = self._pending_fixture(module, "generic")
            row["record"] = dataclasses.replace(
                row["record"],
                stdout=sentinel.encode("ascii") if channel == "child-stdout" else b"",
                stderr=sentinel.encode("ascii") if channel == "child-stderr" else b"",
            )
            try:
                row["pending"].correlate_and_consume_once(
                    row["launched"], (row["record"],), row["closure"],
                    row["interpreter"], row["binding"], row["freshness"],
                )
            except module.PrRouteDenied as exc:
                boundary_rows[channel] = (exc, (sentinel,))
            else:
                self.fail("R5-RAW-CHILD-OUTPUT-AUTHORIZED")

        row = self._pending_fixture(
            module, "generic", remote=remote, destination=destination
        )
        changed_node = dataclasses.replace(
            row["closure"].nodes[0], expected_path=producer_path
        )
        changed_closure = dataclasses.replace(
            row["closure"], nodes=(changed_node,)
        )
        object.__setattr__(row["pending"], "closure", changed_closure)
        row["record"] = dataclasses.replace(
            row["record"], closure_after=changed_closure,
            provenance_verdict="untrusted",
        )
        try:
            row["pending"].correlate_and_consume_once(
                row["launched"], (row["record"],), changed_closure,
                row["interpreter"], row["binding"], row["freshness"],
            )
        except module.PrRouteDenied as exc:
            boundary_rows["binding-producer"] = (
                exc, (remote, destination, producer_path)
            )
        else:
            self.fail("R5-UNTRUSTED-PRODUCER-AUTHORIZED")

        def capture_main(error: BaseException) -> tuple[int, str, str]:
            stdout, stderr = io.StringIO(), io.StringIO()
            with mock.patch.object(
                module._a3_preflight,
                "build_preflight_from_stdin",
                return_value=_heavy_preflight(module),
            ), mock.patch.object(module, "evaluate_heavy", side_effect=error), \
                 contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = module.main()
            return code, stdout.getvalue(), stderr.getvalue()

        for label, (error, sentinels) in boundary_rows.items():
            code, stdout, stderr = capture_main(error)
            self.assertEqual(code, 0)
            combined = stdout + stderr
            with tempfile.TemporaryDirectory(
                prefix="r5-gate-redaction-", dir=scratch
            ) as temp_dir:
                evidence = Path(temp_dir) / "evidence.txt"
                evidence.write_text(combined, encoding="utf-8")
                channels = {
                    "stdout": stdout,
                    "stderr": stderr,
                    "denial": combined,
                    "assertion": f"row={label};output={combined}",
                    "persisted": evidence.read_text(encoding="utf-8"),
                }
            for sentinel in sentinels:
                for channel, rendered in channels.items():
                    with self.subTest(row=label, channel=channel):
                        self.assertNotIn(sentinel, rendered)

        with synthetic_transcript([
            user("push now " + transcript_value)
        ]) as transcript_path:
            envelope = {
                "tool_name": "Bash",
                "tool_input": {
                    "command": "git push origin main # " + command_value
                },
                "transcript_path": str(transcript_path),
            }
            for label, error in (
                ("command-transcript", module.PrRouteDenied("PGG-SCAN-EXECUTION")),
                ("exception", RuntimeError(exception_value)),
            ):
                stdout, stderr = io.StringIO(), io.StringIO()
                with mock.patch.object(
                    module._a3_preflight,
                    "read_stdin_utf8", return_value=json.dumps(envelope)
                ), mock.patch.object(
                    module, "_run_authoritative_scan", side_effect=error
                ), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    self.assertEqual(module.main(), 0)
                combined = stdout.getvalue() + stderr.getvalue()
                sentinels = (
                    command_value, transcript_value,
                    exception_value if label == "exception" else "",
                )
                for sentinel in filter(None, sentinels):
                    with self.subTest(row=label, sentinel=sentinel):
                        self.assertNotIn(sentinel, combined)


class TestPublicationReviewedExceptionGateR2(unittest.TestCase):
    """Closed gate-side layout and qualified-wire contracts for R2."""

    def _module(self):
        return _load_gate_module(CANONICAL_HOOK, "publication_review_gate_r2")

    def _load_contract_module(self, relative_path: str, label: str):
        path = REPO_ROOT / Path(relative_path)
        module_name = f"_publication_review_gate_r2_{label}_{secrets.token_hex(8)}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"R2 test contract module unavailable: {label}")
        loaded = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = loaded
        try:
            spec.loader.exec_module(loaded)
        finally:
            if sys.modules.get(module_name) is loaded:
                del sys.modules[module_name]
        return loaded

    def _policy_module(self):
        return self._load_contract_module(
            "scripts/universal-hooks/scripts/publication_review_policy.py",
            "policy",
        )

    def _scanner_module(self):
        return self._load_contract_module(
            "scripts/universal-hooks/scripts/check-publication-safety.py",
            "scanner",
        )

    @staticmethod
    def _synthetic_repository() -> dict[str, object]:
        import base64

        if os.name == "nt":
            encoding = "windows-utf16le"
            encode_path = lambda value: value.encode("utf-16-le", errors="surrogatepass")
            paths = {
                "commonGit": r"C:\fixture\repo\.git",
                "worktreeGit": r"C:\fixture\repo\.git\worktrees\selected",
                "worktreeRoot": r"C:\fixture\repo",
            }
        else:
            encoding = "posix-bytes"
            encode_path = os.fsencode
            paths = {
                "commonGit": "/fixture/repo/.git",
                "worktreeGit": "/fixture/repo/.git/worktrees/selected",
                "worktreeRoot": "/fixture/repo",
            }
        return {
            "kind": "native-worktree-v1",
            "objectFormat": "sha1",
            **{
                name: {
                    "pathEncoding": encoding,
                    "pathBase64": base64.b64encode(encode_path(path)).decode("ascii"),
                    "device": str(4 + index),
                    "inode": str(5 + index),
                }
                for index, (name, path) in enumerate(paths.items())
            },
        }

    @staticmethod
    def _synthetic_snapshot(policy_module) -> tuple[dict[str, object], str]:
        snapshot = {
            "schemaVersion": 1,
            "status": "absent",
            "origin": None,
            "rawBase64": None,
            "rawSha256": None,
            "diagnostic": "absent",
        }
        return snapshot, policy_module.H(policy_module.DOMAIN_SNAPSHOT, snapshot)

    @staticmethod
    def _review_wire_fields(policy_module, repository: dict[str, object]):
        import base64

        decision_id = "D1"
        record_sha256 = policy_module.H(
            policy_module.DOMAIN_RECORD, {"syntheticTestRecord": decision_id}
        )
        used_list = [[decision_id, record_sha256]]
        used_token = base64.b64encode(policy_module.C(used_list)).decode("ascii")
        repository_sha256 = policy_module.H(
            policy_module.DOMAIN_REPOSITORY, repository
        )
        subject = {
            "repositorySha256": repository_sha256,
            "mode": "range",
            "commitOid": "1" * 40,
            "rawPathBase64": base64.b64encode(b"sample.txt").decode("ascii"),
            "blobOid": "2" * 40,
            "blobSha256": hashlib.sha256(b"abc").hexdigest(),
            "blobByteCount": 3,
            "gitMode": "100644",
        }
        application = {
            "subject": subject,
            "occurrenceSha256": policy_module.H(
                policy_module.DOMAIN_OCCURRENCE,
                {"syntheticTestOccurrence": decision_id},
            ),
            "bindingSha256": policy_module.H(
                policy_module.DOMAIN_BINDING,
                {
                    "decisionId": decision_id,
                    "occurrenceId": "O1",
                    "repositorySha256": repository_sha256,
                },
            ),
            "decisionId": decision_id,
            "recordSha256": record_sha256,
            "occurrenceId": "O1",
        }
        return (
            used_list,
            used_token,
            policy_module.applied_set_digest([application]),
            repository_sha256,
        )

    def _qualified_range_line(
        self, snapshot_id: str, used_token: str, applied_set: str
    ) -> str:
        scanner = self._scanner_module()
        history = scanner.HistoryProof(
            commit_ids=("1" * 40,),
            object_ids=("1" * 40, "2" * 40, "3" * 40),
            blob_ids=("2" * 40,),
            blob_bytes=3,
            text_blobs=1,
            binary_blobs=0,
            subjects=(("1" * 40, b"sample commit", "subject"),),
            paths=(("sample.txt", b"sample"),),
            commit_set="a" * 64,
            object_set="b" * 64,
            blob_set="c" * 64,
            subject_set="d" * 64,
            path_set="e" * 64,
        )
        clean = scanner._serialize_range_receipt_v3(
            history,
            "origin",
            "refs/heads/main",
            "1" * 40,
            "1" * 40,
        )
        self.assertTrue(clean.endswith(")"))
        qualified = clean.replace(
            "publication-safety: clean (range, receipt=v3,",
            "publication-safety: qualified (range, receipt=v3,",
            1,
        )
        return (
            qualified[:-1]
            + f", policy-snapshot={snapshot_id}, used-decisions={used_token}, "
            + f"applied=1, applied-set={applied_set}, unresolved=0, evaluation=complete)\n"
        )

    def test_four_declared_layouts_select_exact_roots_and_eight_roles(self) -> None:
        module = self._module()
        expected = (
            (
                "universal",
                Path("R/scripts/universal-hooks/scripts/check-git-push-gate.py"),
                Path("R/scripts"),
                (
                    ("gate", "universal-hooks/scripts/check-git-push-gate.py"),
                    ("hook_common", "universal-hooks/scripts/hook_common.py"),
                    ("classifier", "universal-hooks/hooks/check-machine-local-path.py"),
                    ("posix_helper", "process_supervision/posix_process_group.py"),
                    ("windows_job", "process_supervision/windows_job.py"),
                    ("scanner", "universal-hooks/scripts/check-publication-safety.py"),
                    ("publication_review_policy", "universal-hooks/scripts/publication_review_policy.py"),
                    ("linked_runtime_subroots", "linked_runtime_subroots.py"),
                ),
            ),
            (
                "codex-source",
                Path("R/src.codex/skills/lead/scripts/check-git-push-gate.py"),
                Path("R"),
                (
                    ("gate", "src.codex/skills/lead/scripts/check-git-push-gate.py"),
                    ("hook_common", "src.codex/skills/lead/scripts/hook_common.py"),
                    ("classifier", "src.codex/skills/lead/hooks/check-machine-local-path.py"),
                    ("posix_helper", "scripts/process_supervision/posix_process_group.py"),
                    ("windows_job", "scripts/process_supervision/windows_job.py"),
                    ("scanner", "src.codex/skills/lead/scripts/check-publication-safety.py"),
                    ("publication_review_policy", "src.codex/skills/lead/scripts/publication_review_policy.py"),
                    ("linked_runtime_subroots", "scripts/linked_runtime_subroots.py"),
                ),
            ),
            (
                "claude-source",
                Path("R/src.claude/agents/scripts/check-git-push-gate.py"),
                Path("R"),
                (
                    ("gate", "src.claude/agents/scripts/check-git-push-gate.py"),
                    ("hook_common", "src.claude/agents/scripts/hook_common.py"),
                    ("classifier", "src.claude/agents/hooks/check-machine-local-path.py"),
                    ("posix_helper", "scripts/process_supervision/posix_process_group.py"),
                    ("windows_job", "scripts/process_supervision/windows_job.py"),
                    ("scanner", "src.claude/agents/scripts/check-publication-safety.py"),
                    ("publication_review_policy", "src.claude/agents/scripts/publication_review_policy.py"),
                    ("linked_runtime_subroots", "scripts/linked_runtime_subroots.py"),
                ),
            ),
            (
                "component",
                Path("R/scripts/check-git-push-gate.py"),
                Path("R"),
                (
                    ("gate", "scripts/check-git-push-gate.py"),
                    ("hook_common", "scripts/hook_common.py"),
                    ("classifier", "hooks/check-machine-local-path.py"),
                    ("posix_helper", "scripts/process_supervision/posix_process_group.py"),
                    ("windows_job", "scripts/process_supervision/windows_job.py"),
                    ("scanner", "scripts/check-publication-safety.py"),
                    ("publication_review_policy", "scripts/publication_review_policy.py"),
                    ("linked_runtime_subroots", "scripts/linked_runtime_subroots.py"),
                ),
            ),
        )
        for name, gate, expected_root, roles in expected:
            with self.subTest(layout=name):
                layout, root = module._layout_for_gate(gate)
                self.assertEqual(name, layout.name)
                self.assertEqual(expected_root, root)
                self.assertEqual(roles, layout.role_paths)

    def test_longest_exact_layout_match_refuses_ambiguity(self) -> None:
        module = self._module()
        original = module.SOURCE_LAYOUTS
        selected = original[0]
        duplicate = module.SourceLayout(
            "duplicate", selected.gate_suffix, selected.trust_root_up,
            selected.role_paths,
        )
        module.SOURCE_LAYOUTS = (*original, duplicate)
        try:
            with self.assertRaisesRegex(ValueError, "layout-ambiguous"):
                module._layout_for_gate(
                    Path("R/scripts/universal-hooks/scripts/check-git-push-gate.py")
                )
        finally:
            module.SOURCE_LAYOUTS = original

    def test_qualified_range_is_exact_and_reuses_v3_graph_validation(self) -> None:
        module = self._module()
        policy = self._policy_module()
        snapshot, snapshot_id = self._synthetic_snapshot(policy)
        repository = self._synthetic_repository()
        _used_list, used_token, applied_set, _repository_sha256 = (
            self._review_wire_fields(policy, repository)
        )
        line = self._qualified_range_line(snapshot_id, used_token, applied_set)
        parsed = module.parse_publication_safety_observation(line)
        self.assertEqual("qualified-v3", parsed.kind)
        self.assertEqual((1, 3, 1, 3, 1, 0, 1, 1), (
            parsed.receipt.commits,
            parsed.receipt.objects,
            parsed.receipt.blobs,
            parsed.receipt.blob_bytes,
            parsed.receipt.text,
            parsed.receipt.binary,
            parsed.receipt.subjects,
            parsed.receipt.paths,
        ))
        self.assertEqual((snapshot_id, used_token, 1, applied_set), (
            parsed.qualification.policy_snapshot_id,
            parsed.qualification.used_decisions_b64,
            parsed.qualification.applied,
            parsed.qualification.applied_set,
        ))
        review_suffix = (
            f", policy-snapshot={snapshot_id}, used-decisions={used_token}, "
            f"applied=1, applied-set={applied_set}, unresolved=0, evaluation=complete"
        )
        self.assertEqual("valid-v3", module.parse_publication_safety_observation(
            line.replace("publication-safety: qualified", "publication-safety: clean")
              .replace(review_suffix, "")
        ).kind)

        observed_crlf = (
            "publication-safety: qualified (range, receipt=v3, commits=2, "
            "commit-set=17f8a309d3c9adc3a9f238406a1154dc62fd961574a3879424c2ad0736e58305, "
            "messages=complete, objects=7, "
            "object-set=938143e23e5f55758922c14c9a26696d7894ea1f3441c04d15c9dfbc58da1580, "
            "blobs=2, "
            "blob-set=e34c4117b9ebb4c489d61cbda9d0b2763d9b7240fc7f1daa1c0aa6206d6870d6, "
            "blob-bytes=643, text=2, binary=0, subjects=3, "
            "subject-set=b470dbf3a92cd7fde9d0dd1c8672d527a12c0a507e2c54325b6bd7706ad71110, "
            "paths=2, "
            "path-set=c22afb23d14ccbef9f72c2774c69b9fc273f7527cdaac0e5f0a8fcc9117fd796, "
            "history=complete, remote=origin, dst=main, "
            "src=37633bada34b0125476e18b0b04ab589382e55f7, "
            "tip=37633bada34b0125476e18b0b04ab589382e55f7, "
            "policy-snapshot=69da51db387f699dbcca0652b84f84f4e7fed1a5b7d0b8d3ac5e6ac090fe34dc, "
            "used-decisions=W1sicWEtcHVibGljYXRpb24tcmV2aWV3ZWQtZml4dHVyZS0yMDI2MTAxNy1yMSIsImU3NWVjZTZlNTg1NDBiZjAxNzJkODYxMmE5MTZkOThkMDhlYzVhYjZhMWRiYWUzYmE3MmZmZGE0YTQwODk0NWUiXV0=, "
            "applied=10, "
            "applied-set=34797494265a28f311671814a249bce26250c2f8464a2040d57ebb28e6bc654c, "
            "unresolved=0, evaluation=complete)\r\n"
        )
        self.assertEqual(1053, len(observed_crlf.encode("ascii")))
        self.assertEqual(
            "qualified-v3",
            module.parse_publication_safety_observation(observed_crlf).kind,
        )
        self.assertEqual(
            module.parse_publication_safety_observation(
                observed_crlf.replace("\r\n", "\n")
            ),
            module.parse_publication_safety_observation(observed_crlf),
        )

        crlf = line.replace("\n", "\r\n")
        self.assertEqual(parsed, module.parse_publication_safety_observation(crlf))

        empty_graph = range_receipt_v3(
            files=0, remote="origin", dst="refs/heads/main",
            src="1" * 40, tip="1" * 40,
        )
        empty_qualified = (
            empty_graph[:-1]
            + f", policy-snapshot={snapshot_id}, used-decisions={used_token}, "
            + f"applied=1, applied-set={applied_set}, unresolved=0, evaluation=complete)\n"
        )
        self.assertEqual(
            "valid-v3", module.parse_publication_safety_observation(
                empty_graph + "\n"
            ).kind,
        )
        self.assertEqual(
            "malformed", module.parse_publication_safety_observation(
                empty_qualified
            ).kind,
        )

        binary_only = range_receipt_v3(
            files=1, remote="origin", dst="refs/heads/main",
            src="1" * 40, tip="1" * 40,
        ).replace("text=1, binary=0", "text=0, binary=1")
        binary_qualified = (
            binary_only[:-1]
            + f", policy-snapshot={snapshot_id}, used-decisions={used_token}, "
            + f"applied=1, applied-set={applied_set}, unresolved=0, evaluation=complete)\n"
        )
        self.assertEqual(
            "valid-v3", module.parse_publication_safety_observation(
                binary_only + "\n"
            ).kind,
        )
        self.assertEqual(
            "malformed", module.parse_publication_safety_observation(
                binary_qualified
            ).kind,
        )

        zero_bytes = line.replace("blob-bytes=3", "blob-bytes=0")
        self.assertEqual("malformed", module.parse_publication_safety_observation(zero_bytes).kind)

        malformed = (
            line[:-1],
            line.replace("\n", "\r"),
            line.replace("\n", "\r\r\n"),
            line + "\n",
            line.replace("evaluation=complete", "unresolved=0, evaluation=complete"),
            line.replace("text=1, binary=0", "text=0, binary=0"),
            line.replace("used-decisions=" + used_token, "used-decisions=AA=A"),
            line + "publication-safety: clean (range, receipt=v3)\n",
        )
        for candidate in malformed:
            with self.subTest(candidate=candidate[:96]):
                self.assertEqual(
                    "malformed",
                    module.parse_publication_safety_observation(candidate).kind,
                )

    def test_staged_qualified_spelling_is_typed_but_not_range_evidence(self) -> None:
        module = self._module()
        policy = self._policy_module()
        snapshot, snapshot_id = self._synthetic_snapshot(policy)
        repository = self._synthetic_repository()
        _used_list, used_token, applied_set, _repository_sha256 = (
            self._review_wire_fields(policy, repository)
        )
        line = (
            "publication-safety: qualified (staged, examined=1, "
            f"policy-snapshot={snapshot_id}, used-decisions={used_token}, "
            f"applied=1, applied-set={applied_set}, unresolved=0, "
            "evaluation=complete)\n"
        )
        parsed = module.parse_publication_safety_observation(line)
        self.assertEqual("qualified-staged", parsed.kind)
        self.assertIsNone(parsed.receipt)
        self.assertEqual("malformed", module.parse_publication_safety_observation(
            line.replace("examined=1", "examined=0")
        ).kind)

    def _qualified_pending_fixture(
        self, *, qualification_snapshot_id=None, stderr=b""
    ):
        module = self._module()
        policy = self._policy_module()
        snapshot, snapshot_id = self._synthetic_snapshot(policy)
        repository = self._synthetic_repository()
        used_list, used_token, applied_set, repository_sha256 = (
            self._review_wire_fields(policy, repository)
        )
        modules = module.CapturedReviewModules(policy, object(), ())
        payload_bytes = policy.C({"syntheticGatePendingFixture": 1})
        captured_review = module.CapturedReviewPayload(
            modules,
            snapshot,
            snapshot_id,
            {"status": "captured", "repository": repository, "diagnostic": "none"},
            repository, True, payload_bytes,
            hashlib.sha256(payload_bytes).hexdigest(),
        )
        row = TestPublicationSafetyTrustedScanR5Proof()._pending_fixture(
            module, "generic", captured_review=captured_review
        )
        qualified = self._qualified_range_line(
            qualification_snapshot_id or snapshot_id,
            used_token,
            applied_set,
        )
        row["record"] = dataclasses.replace(
            row["record"], stdout=qualified.encode("ascii"), stderr=stderr
        )
        row["records"] = (row["record"],)
        finalization = {
            "inputSnapshotId": snapshot_id,
            "usedList": used_list,
            "currentSnapshotId": snapshot_id,
            "repositorySha256": repository_sha256,
            "status": "valid",
            "reason": "none",
            "resourcesSettled": True,
        }
        return module, row, finalization, used_list

    def test_pending_owner_requires_final_used_authority_for_qualified_range(self) -> None:
        fixture = self._qualified_pending_fixture

        module, row, finalization, used_list = fixture()
        finalize_review = mock.Mock(return_value=(finalization, used_list))
        consumed = row["pending"].correlate_and_consume_once(
            row["launched"], row["records"], row["closure"],
            row["interpreter"], row["binding"], row["freshness"],
            finalize_review=finalize_review,
        )
        self.assertEqual("qualified-v3", consumed.parsed_outcome.kind)
        self.assertEqual(finalization, consumed.review_finalization)
        finalize_review.assert_called_once_with(consumed.parsed_outcome.qualification)

        module, row, _finalization, _used_list = fixture()
        with self.assertRaises(module.PrRouteDenied):
            row["pending"].correlate_and_consume_once(
                row["launched"], row["records"], row["closure"],
                row["interpreter"], row["binding"], row["freshness"],
            )

        module, row, finalization, used_list = fixture()
        mismatched_used_list = [["D2", "b" * 64]]
        finalize_review = mock.Mock(
            return_value=(finalization, mismatched_used_list)
        )
        with self.assertRaises(module.PrRouteDenied):
            row["pending"].correlate_and_consume_once(
                row["launched"], row["records"], row["closure"],
                row["interpreter"], row["binding"], row["freshness"],
                finalize_review=finalize_review,
            )
        finalize_review.assert_called_once()

        module, row, finalization, used_list = fixture()
        malformed_result = mock.Mock(return_value=(finalization,))
        with self.assertRaises(module.PrRouteDenied):
            row["pending"].correlate_and_consume_once(
                row["launched"], row["records"], row["closure"],
                row["interpreter"], row["binding"], row["freshness"],
                finalize_review=malformed_result,
            )
        self.assertEqual(row["pending"].state, module.PendingState.FAILED)
        self.assertIsNone(row["pending"].consumption_id)

        module, row, finalization, used_list = fixture(
            qualification_snapshot_id="8" * 64
        )
        finalize_review = mock.Mock(return_value=(finalization, used_list))
        with self.assertRaises(module.PrRouteDenied):
            row["pending"].correlate_and_consume_once(
                row["launched"], row["records"], row["closure"],
                row["interpreter"], row["binding"], row["freshness"],
                finalize_review=finalize_review,
            )
        finalize_review.assert_not_called()

        module, row, finalization, used_list = fixture(stderr=b"extra diagnostic\n")
        finalize_review = mock.Mock(return_value=(finalization, used_list))
        with self.assertRaises(module.PrRouteDenied):
            row["pending"].correlate_and_consume_once(
                row["launched"], row["records"], row["closure"],
                row["interpreter"], row["binding"], row["freshness"],
                finalize_review=finalize_review,
            )
        finalize_review.assert_not_called()

        module, row, finalization, used_list = fixture()
        row["record"] = dataclasses.replace(
            row["record"],
            stdout=row["record"].stdout.replace(b"remote=origin", b"remote=other"),
        )
        row["records"] = (row["record"],)
        finalize_review = mock.Mock(return_value=(finalization, used_list))
        with self.assertRaises(module.PrRouteDenied) as caught:
            row["pending"].correlate_and_consume_once(
                row["launched"], row["records"], row["closure"],
                row["interpreter"], row["binding"], row["freshness"],
                finalize_review=finalize_review,
            )
        self.assertEqual(caught.exception.failure_id, "PGG-RANGE-BINDING")
        finalize_review.assert_not_called()

        module, row, finalization, used_list = fixture()
        stale_finalization = dict(finalization, status="invalid", reason="repository-drift")
        finalize_review = mock.Mock(
            return_value=(stale_finalization, used_list)
        )
        with self.assertRaises(module.PrRouteDenied):
            row["pending"].correlate_and_consume_once(
                row["launched"], row["records"], row["closure"],
                row["interpreter"], row["binding"], row["freshness"],
                finalize_review=finalize_review,
            )
        self.assertEqual(row["pending"].state, module.PendingState.FAILED)
        self.assertIsNone(row["pending"].consumption_id)

    def test_authoritative_scan_correlates_raw_bytes_before_used_finalizer(self) -> None:
        module = self._module()
        fixtures = TestPublicationReviewedExceptionGateR2()
        policy = fixtures._policy_module()
        snapshot, snapshot_id = fixtures._synthetic_snapshot(policy)
        repository = fixtures._synthetic_repository()
        used_list, used_token, applied_set, repository_sha256 = (
            fixtures._review_wire_fields(policy, repository)
        )
        captured_modules = module.CapturedReviewModules(policy, object(), ())
        payload_bytes = policy.C({"syntheticCallerFixture": 1})
        captured_review = module.CapturedReviewPayload(
            captured_modules,
            snapshot,
            snapshot_id,
            {"status": "captured", "repository": repository, "diagnostic": "none"},
            repository, True, payload_bytes,
            hashlib.sha256(payload_bytes).hexdigest(),
        )
        stdout = fixtures._qualified_range_line(
            snapshot_id, used_token, applied_set
        ).encode("ascii")
        finalization = {
            "inputSnapshotId": snapshot_id,
            "usedList": used_list,
            "currentSnapshotId": snapshot_id,
            "repositorySha256": repository_sha256,
            "status": "valid",
            "reason": "none",
            "resourcesSettled": True,
        }
        binding = module.PushScanBinding(
            "generic", "origin", "refs/heads/main", "1" * 40, "1" * 40
        )
        closure = TestPublicationSafetyTrustedScanR3()._closure(module)
        interpreter = closure.interpreter_identity
        fd = os.open(os.devnull, os.O_RDONLY)
        parse_events = []
        finalizer_events = []
        original_parser = module.parse_publication_safety_observation
        qualifications = []

        def record_parse(raw_text):
            parse_events.append(raw_text)
            parsed = original_parser(raw_text)
            if parsed.kind == "qualified-v3":
                qualifications.append(parsed.qualification)
            return parsed

        def record_finalization(actual_review, qualification, *_args):
            finalizer_events.append(qualification)
            self.assertIs(actual_review, captured_review)
            self.assertTrue(qualifications)
            self.assertEqual(qualification, qualifications[-1])
            return finalization, used_list

        def launch_correlated_child(pending, payload, _repository_workdir):
            self.assertEqual(payload, payload_bytes)
            settled = TestPublicationSafetyTrustedScanR5Proof()._pending_fixture(
                module, "generic", captured_review=captured_review
            )
            settled_pending = settled["pending"]
            pending.child_identity = settled_pending.child_identity
            pending.supervisor = settled_pending.supervisor
            pending.settlement = settled_pending.settlement
            pending.state = settled_pending.state
            launched = module.LaunchedScanInvocation(
                pending,
                pending.child_identity,
                pending.supervisor,
                pending.invocation_id,
                pending.attempt_id,
                pending.binding,
                pending.exact_argv,
                pending.result_slot,
            )
            execution = module.TrustedExecutionRecord(
                pending,
                launched,
                pending.result_slot,
                True,
                0,
                stdout,
                b"",
                pending.settlement,
                closure,
                interpreter,
                "trusted",
            )
            return launched, (execution,)

        try:
            with mock.patch.object(
                module, "_capture_source_closure", return_value=((fd,), closure)
            ), mock.patch.object(
                module, "_load_captured_review_modules", return_value=captured_modules
            ), mock.patch.object(
                module, "_capture_review_payload", return_value=captured_review
            ), mock.patch.object(
                module, "_interpreter_identity", return_value=interpreter
            ), mock.patch.object(
                module, "_recheck_source_closure", return_value=closure
            ), mock.patch.object(
                module, "_run_snapshot_child", side_effect=launch_correlated_child
            ), mock.patch.object(
                module, "_refresh_scan_binding", return_value=binding
            ), mock.patch.object(
                module, "parse_publication_safety_observation", side_effect=record_parse
            ) as parser, mock.patch.object(
                module, "_verify_used_review_currentness", side_effect=record_finalization
            ) as finalizer:
                consumed = module._run_authoritative_scan(
                    binding, str(REPO_ROOT.resolve()), "synthetic-git"
                )
        finally:
            try:
                os.fstat(fd)
            except OSError:
                pass
            else:
                os.close(fd)

        self.assertEqual(consumed.parsed_outcome.kind, "qualified-v3")
        self.assertEqual(consumed.review_finalization, finalization)
        self.assertEqual(consumed.execution.pending.state, module.PendingState.CONSUMED)
        self.assertGreater(parser.call_count, 0)
        self.assertEqual(len(finalizer_events), 1)
        self.assertEqual(finalizer_events[0], qualifications[0])
        self.assertEqual(finalizer.call_count, 1)

    def test_v3_pending_does_not_finalize_review_or_reparse_replay(self) -> None:
        module = self._module()
        row = TestPublicationSafetyTrustedScanR5Proof()._pending_fixture(
            module, "generic"
        )
        finalize_review = mock.Mock(side_effect=AssertionError("ordinary V3 finalized"))
        with mock.patch.object(
            module,
            "parse_publication_safety_observation",
            wraps=module.parse_publication_safety_observation,
        ) as parser:
            consumed = row["pending"].correlate_and_consume_once(
                row["launched"], row["records"], row["closure"],
                row["interpreter"], row["binding"], row["freshness"],
                finalize_review=finalize_review,
            )
            self.assertEqual(consumed.parsed_outcome.kind, "valid-v3")
            self.assertEqual(parser.call_count, 1)
            with self.assertRaisesRegex(module.PrRouteDenied, "PGG-RECEIPT-USED"):
                row["pending"].correlate_and_consume_once(
                    row["launched"], row["records"], row["closure"],
                    row["interpreter"], row["binding"], row["freshness"],
                    finalize_review=finalize_review,
                )
            self.assertEqual(parser.call_count, 1)
        finalize_review.assert_not_called()

    def test_finalizer_baseexception_and_deadline_leave_pending_failed(self) -> None:
        module, row, finalization, used_list = self._qualified_pending_fixture()
        callback_error = KeyboardInterrupt("synthetic finalizer cancellation")
        finalize_review = mock.Mock(side_effect=callback_error)
        with self.assertRaises(KeyboardInterrupt) as caught:
            row["pending"].correlate_and_consume_once(
                row["launched"], row["records"], row["closure"],
                row["interpreter"], row["binding"], row["freshness"],
                finalize_review=finalize_review,
            )
        self.assertIs(caught.exception, callback_error)
        self.assertEqual(row["pending"].state, module.PendingState.FAILED)
        self.assertIsNone(row["pending"].consumption_id)

        module, row, finalization, used_list = self._qualified_pending_fixture()
        now = time.monotonic()
        object.__setattr__(row["pending"], "authorization_deadline", now + 0.5)
        finalize_review = mock.Mock(return_value=(finalization, used_list))
        with mock.patch.object(module.time, "monotonic", side_effect=(now, now + 1.0)):
            with self.assertRaisesRegex(module.PrRouteDenied, "PGG-SCAN-CORRELATION"):
                row["pending"].correlate_and_consume_once(
                    row["launched"], row["records"], row["closure"],
                    row["interpreter"], row["binding"], row["freshness"],
                    finalize_review=finalize_review,
                )
        finalize_review.assert_called_once()
        self.assertEqual(row["pending"].state, module.PendingState.FAILED)
        self.assertIsNone(row["pending"].consumption_id)

    def test_process_owner_settles_child_when_reader_start_is_interrupted(self) -> None:
        module = self._module()
        children = []
        real_popen = module.subprocess.Popen

        def capture_popen(*args, **kwargs):
            child = real_popen(*args, **kwargs)
            children.append(child)
            return child

        def interrupt_start(_thread):
            raise KeyboardInterrupt("controlled reader-start interruption")

        try:
            with mock.patch.object(module.subprocess, "Popen", side_effect=capture_popen), \
                 mock.patch.object(
                     module.threading.Thread, "start", autospec=True,
                     side_effect=interrupt_start,
                 ):
                with self.assertRaisesRegex(KeyboardInterrupt, "reader-start") as caught:
                    module._run_process(
                        [sys.executable, "-c", "import time; time.sleep(30)"],
                        5.0,
                        os.getcwd(),
                    )
                self.assertEqual(len(children), 1)
                child = children[0]
                before_fixture_rescue = {
                    "returncode": child.poll(),
                    "stdoutClosed": child.stdout.closed,
                    "stderrClosed": child.stderr.closed,
                }
                self.assertIsNotNone(before_fixture_rescue["returncode"])
                self.assertTrue(before_fixture_rescue["stdoutClosed"])
                self.assertTrue(before_fixture_rescue["stderrClosed"])
                owner_outcome = getattr(
                    caught.exception, "publication_gate_process_outcome", None
                )
                self.assertIsInstance(owner_outcome, dict)
                self.assertTrue(owner_outcome["resourcesSettled"])
        finally:
            if children:
                child = children[0]
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=5.0)
                if child.stdout is not None and not child.stdout.closed:
                    child.stdout.close()
                if child.stderr is not None and not child.stderr.closed:
                    child.stderr.close()

        self.assertEqual(1, len(children))
        self.assertIsNotNone(children[0].poll())
        self.assertTrue(children[0].stdout.closed)
        self.assertTrue(children[0].stderr.closed)

    def test_source_node_and_interpreter_close_acquired_fds_on_cancellation(self) -> None:
        module = self._module()
        real_open_owned = module._open_owned_descriptor

        with tempfile.TemporaryDirectory(prefix="gate-owned-fd-") as directory:
            source = Path(directory) / "source.py"
            source.write_bytes(b"synthetic source bytes\n")
            for exception_type in (KeyboardInterrupt, SystemExit):
                opened = []

                def capture_open(open_descriptor, owned_fds):
                    fd = real_open_owned(open_descriptor, owned_fds)
                    opened.append(fd)
                    return fd

                with self.subTest(owner="source-node", exception=exception_type.__name__):
                    try:
                        with mock.patch.object(
                            module, "_open_owned_descriptor", side_effect=capture_open
                        ), mock.patch.object(
                            module.os,
                            "read",
                            side_effect=exception_type("injected source read cancellation"),
                        ):
                            with self.assertRaises(exception_type):
                                module._capture_source_node(source, "fixture")
                        self.assertEqual(len(opened), 1)
                        with self.assertRaises(OSError):
                            os.fstat(opened[0])
                    finally:
                        for fd in opened:
                            try:
                                os.fstat(fd)
                            except OSError:
                                pass
                            else:
                                os.close(fd)

            opened = []
            interpreter_identity = module._interpreter_identity()

            def capture_interpreter_open(open_descriptor, owned_fds):
                fd = real_open_owned(open_descriptor, owned_fds)
                opened.append(fd)
                return fd

            def cancel_identity(_metadata):
                raise KeyboardInterrupt("injected interpreter identity cancellation")

            try:
                with mock.patch.object(
                    module, "_open_owned_descriptor", side_effect=capture_interpreter_open
                ), mock.patch.object(
                    module, "_stat_identity", side_effect=cancel_identity
                ):
                    with self.assertRaisesRegex(KeyboardInterrupt, "interpreter identity"):
                        module._capture_interpreter_handle(interpreter_identity)
                self.assertEqual(len(opened), 1)
                with self.assertRaises(OSError):
                    os.fstat(opened[0])
            finally:
                for fd in opened:
                    try:
                        os.fstat(fd)
                    except OSError:
                        pass
                    else:
                        os.close(fd)

    def test_component_capture_attempts_every_close_and_retains_primary(self) -> None:
        module = self._module()
        real_open_owned = module._open_owned_descriptor
        real_directory_identity = module._directory_identity
        real_close = os.close
        with tempfile.TemporaryDirectory(prefix="gate-components-") as directory:
            root = Path(directory)
            (root / "sub").mkdir()
            opened = []
            close_attempts = []

            def capture_open(open_descriptor, owned_fds):
                fd = real_open_owned(open_descriptor, owned_fds)
                opened.append(fd)
                return fd

            def interrupt_after_second_open(metadata):
                if len(opened) == 2:
                    raise SystemExit("injected component identity cancellation")
                return real_directory_identity(metadata)

            def fail_first_close(fd):
                close_attempts.append(fd)
                if len(close_attempts) == 1:
                    raise OSError("injected close failure")
                return real_close(fd)

            try:
                with mock.patch.object(
                    module, "_open_owned_descriptor", side_effect=capture_open
                ), mock.patch.object(
                    module, "_directory_identity", side_effect=interrupt_after_second_open
                ), mock.patch.object(os, "close", side_effect=fail_first_close):
                    with self.assertRaisesRegex(SystemExit, "component identity") as caught:
                        module._capture_path_components(
                            root, (root / "sub" / "fixture.py",)
                        )
                    self.assertEqual(len(opened), 2)
                    self.assertEqual(set(close_attempts), set(opened))
                    failures = getattr(
                        caught.exception,
                        "publication_gate_descriptor_cleanup_failures",
                        (),
                    )
                    self.assertEqual(len(failures), 1)
                    failed_fd, failure = failures[0]
                    self.assertIsInstance(failure, OSError)
                    self.assertIn(failed_fd, opened)
                    for fd in opened:
                        if fd == failed_fd:
                            os.fstat(fd)
                        else:
                            with self.assertRaises(OSError):
                                os.fstat(fd)
            finally:
                for fd in opened:
                    try:
                        os.fstat(fd)
                    except OSError:
                        pass
                    else:
                        real_close(fd)

    def test_closure_owner_closes_prior_nodes_when_interpreter_capture_cancels(self) -> None:
        module = self._module()
        real_interpreter_capture = module._capture_interpreter_handle
        opened = []

        def interrupt_after_interpreter(identity, *, owned_fds=None):
            fd = real_interpreter_capture(identity, owned_fds=owned_fds)
            opened.extend(tuple(owned_fds or ()))
            raise KeyboardInterrupt("injected aggregate capture cancellation")

        try:
            with mock.patch.object(
                module,
                "_capture_interpreter_handle",
                side_effect=interrupt_after_interpreter,
            ):
                with self.assertRaisesRegex(KeyboardInterrupt, "aggregate capture"):
                    module._capture_source_closure()
            self.assertGreater(len(opened), len(module.SOURCE_ROLE_ORDER))
            for fd in opened:
                with self.assertRaises(OSError):
                    os.fstat(fd)
        finally:
            for fd in opened:
                try:
                    os.fstat(fd)
                except OSError:
                    pass
                else:
                    os.close(fd)

    @unittest.skipUnless(os.name == "nt", "Windows native handle ownership")
    def test_windows_native_handle_transfer_cancellation_is_retained_as_uncertain(self) -> None:
        import ctypes
        import msvcrt
        from ctypes import wintypes

        module = self._module()
        with tempfile.TemporaryDirectory(prefix="gate-native-handle-") as directory:
            source = Path(directory) / "source.py"
            source.write_bytes(b"synthetic source bytes\n")
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            create = kernel.CreateFileW
            create.argtypes = (
                wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
            )
            create.restype = wintypes.HANDLE
            close = kernel.CloseHandle
            close.argtypes = (wintypes.HANDLE,)
            close.restype = wintypes.BOOL
            opened_handles = []
            close_calls = []

            def observed_create(*args):
                handle = create(*args)
                opened_handles.append(handle)
                return handle

            observed_create.argtypes = create.argtypes
            observed_create.restype = create.restype

            class KernelProxy:
                def __init__(self):
                    self.CreateFileW = observed_create

                def CloseHandle(self, handle):
                    close_calls.append(int(handle))
                    return close(handle)

            proxy = KernelProxy()
            cancellation = KeyboardInterrupt("controlled CRT handle transfer interruption")
            with mock.patch.object(
                ctypes, "WinDLL", return_value=proxy
            ), mock.patch.object(
                msvcrt, "open_osfhandle", side_effect=cancellation
            ):
                with self.assertRaises(KeyboardInterrupt) as caught:
                    module._open_windows_path(source, directory=False, owned_fds=[])
            close_attempted = set()
            try:
                self.assertEqual(len(opened_handles), 1)
                self.assertEqual(close_calls, [])
                self.assertEqual(
                    getattr(
                        caught.exception, "publication_gate_native_handle_outcome", None
                    ),
                    {
                        "handle": int(opened_handles[0]),
                        "ownership": "uncertain-during-crt-transfer",
                        "closeAttempted": False,
                    },
                )
                for handle in opened_handles:
                    close_attempted.add(int(handle))
                    self.assertTrue(close(handle))
            finally:
                # The injected open_osfhandle failed before consuming the actual
                # handle; this fixture is the only owner authorized to rescue it.
                for handle in opened_handles:
                    if int(handle) not in close_attempted:
                        close_attempted.add(int(handle))
                        close(handle)

    def _snapshot_child_pending(self, module, payload: bytes, argv: tuple[str, ...]):
        captured_modules = module.CapturedReviewModules(object(), object(), ())
        captured = module.CapturedReviewPayload(
            captured_modules, {}, "c" * 64, {}, None, False,
            payload, hashlib.sha256(payload).hexdigest(),
        )
        interpreter = module._interpreter_identity()
        binding = module.PushScanBinding(
            "generic", "origin", "refs/heads/main", "1" * 40, "1" * 40
        )
        return module.PendingScanInvocation(
            "child-fixture", "child-attempt", binding, None, interpreter,
            argv, object(), captured,
        )

    def _rescue_child_fixture(self, children) -> None:
        for child in children:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5.0)
            for stream in (child.stdin, child.stdout, child.stderr):
                if stream is not None and not stream.closed:
                    stream.close()

    def test_snapshot_child_settles_state_and_constructor_failures_before_rescue(self) -> None:
        for failure in ("non-prepared", "thread-constructor"):
            module = self._module()
            children = []
            payload = b"synthetic bound child input\n"
            pending = self._snapshot_child_pending(
                module,
                payload,
                (sys.executable, "-c", "import time; time.sleep(30)"),
            )
            if failure == "non-prepared":
                pending.state = module.PendingState.FAILED
            original_popen = module.subprocess.Popen
            cancellation = KeyboardInterrupt("controlled thread constructor interruption")

            def capture_popen(*args, **kwargs):
                child = original_popen(*args, **kwargs)
                children.append(child)
                return child

            constructor = mock.patch.object(
                module.threading, "Thread", side_effect=cancellation
            ) if failure == "thread-constructor" else contextlib.nullcontext()
            try:
                with mock.patch.object(
                    module.subprocess, "Popen", side_effect=capture_popen
                ), constructor:
                    expected = (
                        KeyboardInterrupt
                        if failure == "thread-constructor"
                        else module.PrRouteDenied
                    )
                    with self.assertRaises(expected) as caught:
                        module._run_snapshot_child(pending, payload, os.getcwd())

                self.assertEqual(len(children), 1)
                child = children[0]
                outcome = getattr(caught.exception, "publication_gate_child_outcome", None)
                self.assertIsInstance(outcome, dict)
                self.assertIs(outcome["process"], child)
                self.assertIs(outcome["supervisor"].process, child)
                self.assertIsNotNone(child.poll())
                self.assertTrue(all(
                    stream is None or stream.closed
                    for stream in (child.stdin, child.stdout, child.stderr)
                ))
                self.assertTrue(outcome["settlement"].complete)
                self.assertEqual(pending.state, module.PendingState.FAILED)
                if failure == "thread-constructor":
                    self.assertIs(outcome["supervisor"], pending.supervisor)
                    self.assertIs(caught.exception, cancellation)
                else:
                    self.assertIsNone(pending.supervisor)
                    self.assertEqual(
                        caught.exception.failure_id, "PGG-SCAN-CORRELATION"
                    )
            finally:
                self._rescue_child_fixture(children)

    def test_snapshot_child_observes_uncertain_worker_start_and_settles_before_rescue(self) -> None:
        module = self._module()
        children = []
        payload = b"synthetic bound child input\n"
        pending = self._snapshot_child_pending(
            module,
            payload,
            (sys.executable, "-c", "import time; time.sleep(30)"),
        )
        original_popen = module.subprocess.Popen
        original_start = module.threading.Thread.start
        cancellation = KeyboardInterrupt("controlled post-start interruption")
        start_calls = 0

        def capture_popen(*args, **kwargs):
            child = original_popen(*args, **kwargs)
            children.append(child)
            return child

        def start_then_interrupt_on_reader(worker):
            nonlocal start_calls
            start_calls += 1
            original_start(worker)
            if start_calls == 2:
                raise cancellation

        try:
            with mock.patch.object(
                module.subprocess, "Popen", side_effect=capture_popen
            ), mock.patch.object(
                module.threading.Thread, "start", autospec=True,
                side_effect=start_then_interrupt_on_reader,
            ):
                with self.assertRaises(KeyboardInterrupt) as caught:
                    module._run_snapshot_child(pending, payload, os.getcwd())

            self.assertIs(caught.exception, cancellation)
            self.assertEqual(len(children), 1)
            child = children[0]
            outcome = getattr(caught.exception, "publication_gate_child_outcome", None)
            self.assertIsInstance(outcome, dict)
            self.assertIsNotNone(child.poll())
            self.assertTrue(all(
                stream is None or stream.closed
                for stream in (child.stdin, child.stdout, child.stderr)
            ))
            settlement = outcome["settlement"]
            self.assertTrue(settlement.complete)
            workers = {row["name"]: row for row in outcome["workers"]}
            self.assertEqual(workers["stdout"]["start"], "starting")
            worker_rows = {
                row.worker_identity: row for row in settlement.certificate.workers
            }
            self.assertEqual(
                worker_rows[id(workers["stdout"]["worker"])].terminal, "joined"
            )
            self.assertFalse(settlement.execution_eligible)
        finally:
            self._rescue_child_fixture(children)

    def test_snapshot_child_keeps_precreation_start_interruption_unobserved(self) -> None:
        module = self._module()
        children = []
        payload = b"synthetic bound child input\n"
        pending = self._snapshot_child_pending(
            module,
            payload,
            (sys.executable, "-c", "import time; time.sleep(30)"),
        )
        original_popen = module.subprocess.Popen
        cancellation = KeyboardInterrupt("controlled precreation worker-start interruption")
        start_calls = 0

        def capture_popen(*args, **kwargs):
            child = original_popen(*args, **kwargs)
            children.append(child)
            return child

        def interrupt_before_creation(_worker):
            nonlocal start_calls
            start_calls += 1
            raise cancellation

        try:
            with mock.patch.object(
                module.subprocess, "Popen", side_effect=capture_popen
            ), mock.patch.object(
                module.threading.Thread, "start", autospec=True,
                side_effect=interrupt_before_creation,
            ):
                with self.assertRaises(KeyboardInterrupt) as caught:
                    module._run_snapshot_child(pending, payload, os.getcwd())

            self.assertIs(caught.exception, cancellation)
            self.assertEqual(start_calls, 1)
            self.assertEqual(len(children), 1)
            child = children[0]
            outcome = getattr(caught.exception, "publication_gate_child_outcome", None)
            self.assertIsInstance(outcome, dict)
            self.assertIs(outcome["process"], child)
            self.assertIs(outcome["supervisor"], pending.supervisor)
            self.assertIs(outcome["supervisor"].process, child)

            worker = outcome["workers"][0]
            self.assertEqual(worker["start"], "starting")
            self.assertFalse(worker["worker"].is_alive())
            self.assertIsNone(worker["worker"].ident)
            self.assertIsNone(worker["worker"].native_id)
            worker_row = outcome["settlement"].certificate.workers[0]
            self.assertEqual(worker_row.worker_identity, id(worker["worker"]))
            self.assertEqual(worker_row.start, "starting")
            self.assertEqual(worker_row.terminal, "unobserved")
            self.assertFalse(outcome["settlement"].complete)
            self.assertEqual(
                outcome["settlement"].state,
                module.GateSettlementState.FAILED_UNSETTLED,
            )
            self.assertFalse(outcome["settlement"].execution_eligible)
            self.assertIsNotNone(child.poll())
            self.assertTrue(all(
                stream is None or not stream.closed
                for stream in (child.stdin, child.stdout, child.stderr)
            ))
            self.assertEqual(pending.state, module.PendingState.FAILED)
        finally:
            self._rescue_child_fixture(children)

    def test_snapshot_child_timeout_settles_blocked_stdin_before_buffered_close(self) -> None:
        module = self._module()
        children = []
        payload = b"x" * (16 * 1024 * 1024)
        with tempfile.TemporaryDirectory(prefix="gate-child-ready-") as directory:
            marker = Path(directory) / "ready"
            child_code = (
                "import os; from pathlib import Path; import time; "
                "os.write(1, b'READY\\n'); "
                f"Path({str(marker)!r}).write_text('ready', encoding='ascii'); "
                "time.sleep(30)"
            )
            pending = self._snapshot_child_pending(
                module,
                payload,
                (sys.executable, "-c", child_code),
            )
            original_popen = module.subprocess.Popen
            failure_rows = []

            def capture_popen(*args, **kwargs):
                child = original_popen(*args, **kwargs)
                children.append(child)
                return child

            def run_owner():
                try:
                    module._run_snapshot_child(pending, payload, os.getcwd())
                except BaseException as exc:
                    failure_rows.append(exc)

            owner = threading.Thread(target=run_owner)
            try:
                with mock.patch.object(
                    module.subprocess, "Popen", side_effect=capture_popen
                ), mock.patch.object(module, "SCAN_TIMEOUT_SECONDS", 0.5):
                    owner.start()
                    marker_deadline = time.monotonic() + 5.0
                    while not marker.exists() and time.monotonic() < marker_deadline:
                        time.sleep(0.01)
                    self.assertTrue(marker.exists(), "child did not reach its nonreading state")
                    self.assertEqual(len(children), 1)
                    child = children[0]
                    pending_deadline = time.monotonic() + 2.0
                    while (
                        pending.supervisor is None
                        or not pending.supervisor.workers
                    ) and time.monotonic() < pending_deadline:
                        time.sleep(0.01)
                    self.assertIsNotNone(pending.supervisor)
                    self.assertTrue(pending.supervisor.workers)
                    feeder = pending.supervisor.workers[0].worker
                    self.assertTrue(feeder.is_alive())
                    time.sleep(0.1)
                    self.assertTrue(feeder.is_alive())
                    owner.join(timeout=8.0)
                    before_fixture_rescue = {
                        "ownerAlive": owner.is_alive(),
                        "returncode": child.poll(),
                        "streamsClosed": tuple(
                            stream is None or stream.closed
                            for stream in (child.stdin, child.stdout, child.stderr)
                        ),
                    }
                    self.assertFalse(before_fixture_rescue["ownerAlive"])
                    self.assertIsNotNone(before_fixture_rescue["returncode"])
                    self.assertTrue(all(before_fixture_rescue["streamsClosed"]))
                    self.assertEqual(len(failure_rows), 1)
                    failure = failure_rows[0]
                    outcome = getattr(failure, "publication_gate_child_outcome", None)
                    if outcome is None:
                        self.assertIsInstance(failure, module.PrRouteDenied)
                        self.assertEqual(failure.failure_id, "PGG-SCAN-EXECUTION")
                        self.assertIsNotNone(failure.__cause__)
                        outcome = getattr(
                            failure.__cause__, "publication_gate_child_outcome", None
                        )
                    self.assertIsInstance(outcome, dict)
                    self.assertIs(outcome["process"], child)
                    self.assertEqual(outcome["childIdentity"], child.pid)
                    self.assertFalse(outcome["boundedCompletion"])
                    self.assertEqual(outcome["stdout"], b"READY\n")
                    self.assertEqual(outcome["stderr"], b"")
                    self.assertTrue(outcome["settlement"].complete)
                    settlement_workers = {
                        row.worker_identity: row
                        for row in outcome["settlement"].certificate.workers
                    }
                    self.assertEqual(len(outcome["workers"]), 3)
                    for worker in outcome["workers"]:
                        self.assertIn(
                            settlement_workers[id(worker["worker"])].terminal,
                            {"joined", "not-started"},
                        )
                    self.assertEqual(pending.state, module.PendingState.FAILED)
            finally:
                if owner.ident is not None and owner.is_alive():
                    self._rescue_child_fixture(children)
                    owner.join(timeout=5.0)
                self._rescue_child_fixture(children)


class TestSafeProcessFailureMetadata(unittest.TestCase):
    def module(self):
        return _load_gate_module(CANONICAL_HOOK, "safe_process_failure_" + secrets.token_hex(4))

    def assert_safe_denial(self, module, failure, kind):
        self.assertEqual(failure.failure_id, "PRG-WORKDIR-INVALID")
        metadata, outcome = module._safe_process_failure(failure)
        self.assertEqual(metadata["kind"], kind)
        self.assertEqual(set(outcome), {"returncode", "stdout", "stderr", "complete", "resourcesSettled"})
        self.assertTrue(outcome["resourcesSettled"])
        output = io.StringIO()
        with mock.patch.object(module, "evaluate_heavy", side_effect=failure), contextlib.redirect_stdout(output):
            self.assertEqual(module.compose_gate_result(_heavy_preflight(module)), 0)
        payload = json.loads(output.getvalue())["hookSpecificOutput"]
        self.assertEqual(payload["permissionDecision"], "deny")
        self.assertIn("kind=" + kind, payload["permissionDecisionReason"])
        self.assertNotIn("PRIVATE_PROCESS_CANARY", output.getvalue())
        self.assertNotIn(str(REPO_ROOT), output.getvalue())
        return metadata, outcome

    def test_real_root_nonzero_spawn_and_legacy_none(self):
        module = self.module()
        root = str(REPO_ROOT.resolve())
        git = str(Path(shutil.which("git")).resolve(strict=True))
        self.assertEqual(module._prove_repository_root(root, git, source="tool"), root)
        diagnostic = module.WorkdirDiagnostic("repository-root-proof", "root-output", "repository", "tool", "string")
        with self.assertRaises(module.PrRouteDenied) as raised:
            module._run_text([sys.executable, "-c", "import sys;sys.stderr.write('PRIVATE_PROCESS_CANARY');sys.exit(7)"],
                             time.monotonic() + 5, "PRG-WORKDIR-INVALID", root, workdir_diagnostic=diagnostic)
        metadata, outcome = self.assert_safe_denial(module, raised.exception, "exit-code")
        self.assertEqual(outcome["returncode"], 7)
        self.assertEqual(outcome["stderr"], b"PRIVATE_PROCESS_CANARY")
        self.assertTrue(outcome["complete"])
        self.assertEqual(raised.exception.workdir_diagnostic.source, "tool")
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(module.PrRouteDenied) as raised:
                module._run_text([str(Path(temporary) / "missing-program.exe")], time.monotonic() + 5,
                                 "PRG-WORKDIR-INVALID", root, workdir_diagnostic=diagnostic)
            metadata, outcome = self.assert_safe_denial(module, raised.exception, "spawn-oserror")
            self.assertIsInstance(raised.exception.__cause__, OSError)
            self.assertEqual(metadata["errno"], raised.exception.__cause__.errno)
            self.assertIsNone(outcome["returncode"])
            self.assertFalse(outcome["complete"])
        with mock.patch.object(module, "_run_process", return_value=None):
            with self.assertRaises(module.PrRouteDenied) as raised:
                module._run_text(["legacy-none"], time.monotonic() + 5, "PRG-WORKDIR-INVALID", root,
                                 workdir_diagnostic=diagnostic)
        self.assertEqual(raised.exception.workdir_diagnostic.check, "process-result")
        self.assertIsNone(module._safe_process_failure(raised.exception))
        self.assertEqual(module._format_process_failure(raised.exception), "")

    def test_deadline_reader_and_cleanup_remain_denied_and_settled(self):
        module = self.module()
        root = str(REPO_ROOT.resolve())
        with self.assertRaises(module.PrRouteDenied) as raised:
            module._run_text([sys.executable, "-c", "import time;time.sleep(5)"],
                             time.monotonic() + 0.05, "PRG-WORKDIR-INVALID", root)
        self.assert_safe_denial(module, raised.exception, "deadline")
        actual_popen = module.subprocess.Popen
        for fault, kind in (("reader", "reader-loss"), ("close", "cleanup")):
            children = []
            class Stream:
                def __init__(self, source): self.source = source
                @property
                def closed(self): return self.source.closed
                def read(self, size):
                    if fault == "reader": raise OSError(5, "PRIVATE_PROCESS_CANARY")
                    return self.source.read(size)
                def close(self):
                    self.source.close()
                    if fault == "close": raise OSError(5, "PRIVATE_PROCESS_CANARY")
            def popen(*args, **kwargs):
                child = actual_popen(*args, **kwargs)
                child.stdout = Stream(child.stdout)
                children.append(child)
                return child
            with self.subTest(fault=fault), mock.patch.object(module.subprocess, "Popen", side_effect=popen):
                with self.assertRaises(module.PrRouteDenied) as raised:
                    module._run_text([sys.executable, "-c", "print('owned diagnostic child')"],
                                     time.monotonic() + 5, "PRG-WORKDIR-INVALID", root)
                metadata, outcome = self.assert_safe_denial(module, raised.exception, kind)
                self.assertEqual(metadata["errno"], 5)
                self.assertFalse(outcome["complete"])
                self.assertEqual(len(children), 1)
                self.assertIsNotNone(children[0].poll())
                self.assertTrue(children[0].stdout.closed)
                self.assertTrue(children[0].stderr.closed)

    def test_query_caller_keeps_refusal_and_cancellation_contract(self):
        module = self.module()
        policy = _load_exact_module(CANONICAL_HOOK.parent / "publication_review_policy.py", "diagnostic_query_policy")
        root = REPO_ROOT.resolve()
        outcome = {"returncode": None, "stdout": b"partial", "stderr": b"PRIVATE_PROCESS_CANARY",
                   "complete": False, "resourcesSettled": True}
        failure = OSError(2, "PRIVATE_PROCESS_CANARY")
        module._retain_process_failure(failure, outcome, "spawn-oserror", control_origin="former-none")
        observed = []
        def receive(plan, results):
            observed.extend(results)
            return {"status": "unavailable", "repository": None, "diagnostic": "query-execution-error"}
        with mock.patch.object(module, "_run_process", side_effect=failure), mock.patch.object(policy, "repository_from_query_results", side_effect=receive):
            result = module._capture_repository_observation(policy, root, "synthetic-git")
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(len(observed), len(module.REPOSITORY_QUERY_ORDER))
        self.assertTrue(all(not row.complete and row.resources_settled for row in observed))
        self.assertTrue(all(row.stderr == b"PRIVATE_PROCESS_CANARY" for row in observed))
        cancellation = KeyboardInterrupt("PRIVATE_PROCESS_CANARY")
        module._retain_process_failure(cancellation, outcome, "cancelled")
        with mock.patch.object(module, "_run_process", side_effect=cancellation):
            with self.assertRaises(KeyboardInterrupt) as raised:
                module._capture_repository_observation(policy, root, "synthetic-git")
        self.assertIs(raised.exception, cancellation)
        self.assertEqual(cancellation.publication_review_query_results[-1].failure_kind, "cancelled")


if __name__ == "__main__":
    unittest.main()
