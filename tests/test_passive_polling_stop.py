"""Regression tests for passive-polling Stop hook enforcement."""

from __future__ import annotations

import ast
import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATHS = (
    REPO_ROOT / "scripts" / "universal-hooks" / "scripts" / "check-passive-polling-stop.py",
    REPO_ROOT / "src.claude" / "agents" / "scripts" / "check-passive-polling-stop.py",
    REPO_ROOT / "src.codex" / "skills" / "lead" / "scripts" / "check-passive-polling-stop.py",
)

def entry(role: str, content: object) -> dict[str, object]:
    return {"type": role, "message": {"role": role, "content": content}}


def tool_entry(name: str, tool_input: object) -> dict[str, object]:
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [{"type": "tool_use", "name": name, "input": tool_input}],
        },
    }


def tool_result_entry(text: str) -> dict[str, object]:
    # Claude Code records tool OUTPUT under role=user (`{"type":"user",...}`).
    # This is the entry shape that used to break the "current turn" boundary
    # (see test_probe_followed_by_a_real_tool_result_still_allows_stop below).
    return {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "content": text}]}}


def write_transcript(entries: list[dict[str, object]], directory: Path) -> Path:
    path = directory / "transcript.jsonl"
    path.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in entries) + "\n",
        encoding="utf-8",
    )
    return path


def opaque_pair(body: object, *, call_id: str = "probe-1", input_text: str = 'text(await tools.exec_command({cmd:"Get-Date -Format o","workdir":"<repo>","max_output_tokens":100}));\n') -> list[dict]:
    """Sanitized observed Codex transport; its JavaScript input stays opaque."""
    return [
        {"type": "response_item", "payload": {
            "type": "custom_tool_call", "status": "completed", "call_id": call_id,
            "name": "exec", "input": input_text,
        }},
        {"type": "response_item", "payload": {
            "type": "custom_tool_call_output", "call_id": call_id, "output": [
                {"type": "input_text", "text": "Script completed\nWall time 0.8 seconds\nOutput:\n"},
                {"type": "input_text", "text": body if isinstance(body, str) else json.dumps(body)},
            ],
        }},
    ]


def shell_receipt(**changes: object) -> dict:
    return {"chunk_id": "synthetic", "wall_time_seconds": 0.1736557,
            "exit_code": 0, "original_token_count": 9,
            "output": "2026-10-05T22:23:16.1003644+03:00\r\n", **changes}


class TestPassivePollingStop(unittest.TestCase):
    def run_hook(
        self,
        message: str | None = "Жду ответа бота",
        transcript_entries: list[dict[str, object]] | None = None,
        extra_envelope: dict[str, object] | None = None,
        extra_env: dict[str, str] | None = None,
        raw_stdin: str | None = None,
    ) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory(prefix="passive-stop-test-") as tmp:
            tmp_path = Path(tmp)
            envelope: dict[str, object] = {}
            if transcript_entries is not None:
                envelope["transcript_path"] = str(write_transcript(transcript_entries, tmp_path))
            if message is not None:
                envelope["last_assistant_message"] = message
            if extra_envelope:
                envelope.update(extra_envelope)

            stdin_text = raw_stdin if raw_stdin is not None else json.dumps(envelope, ensure_ascii=False)
            env = os.environ.copy()
            env.pop("ORCHESTRARIUM_DISPATCHED_REVIEW", None)
            if extra_env:
                env.update(extra_env)
            results: list[subprocess.CompletedProcess] = []
            for script in SCRIPT_PATHS:
                with self.subTest(script=script):
                    # encoding="utf-8" forces subprocess to encode input + decode
                    # output as UTF-8 regardless of the parent process's locale.
                    # Production runtimes (Claude Code, Codex CLI) send the hook
                    # envelope as UTF-8 JSON; if the test ran with text=True only,
                    # the parent's locale (cp1251 on Russian Windows) would encode
                    # the stdin bytes and the hook script's UTF-8 decode would
                    # mojibake the Cyrillic, silently breaking polling detection.
                    result = subprocess.run(
                        [sys.executable, str(script)],
                        input=stdin_text,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        env=env,
                    )
                    results.append(result)
                    self.assertEqual(result.returncode, 0, result.stderr)
            return results[-1]

    def assert_allowed(self, result: subprocess.CompletedProcess) -> None:
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def assert_passive_blocked(self, result: subprocess.CompletedProcess) -> None:
        payload = json.loads(result.stdout)
        self.assertEqual(payload["decision"], "block")
        self.assertIn("passive-polling Stop guard", payload["reason"])

    def test_last_assistant_message_without_polling_phrase_allows_stop(self) -> None:
        result = self.run_hook(
            message="Verification finished; tests are listed below.",
            transcript_entries=[entry("user", "status?")],
        )
        self.assert_allowed(result)

        reentry = self.run_hook(
            message="Verification finished; tests are listed below.",
            transcript_entries=[entry("user", "status?")],
            extra_envelope={"stop_hook_active": True},
        )
        self.assert_allowed(reentry)

    def test_standalone_answer_pause_and_nonpassive_pending_allow_stop(self) -> None:
        for message in (
            "The answer is 42.",
            "Paused as requested; no further action taken.",
            "Implementation work remains; another local step is available.",
        ):
            with self.subTest(message=message):
                self.assert_allowed(
                    self.run_hook(
                        message=message,
                        transcript_entries=[entry("user", "request")],
                    )
                )
                self.assert_allowed(
                    self.run_hook(
                        message=message,
                        transcript_entries=[entry("user", "request")],
                        extra_envelope={"stop_hook_active": True},
                    )
                )

    def test_nonpassive_handoff_and_override_text_allow_stop(self) -> None:
        for message in (
            "Let me know if you want more detail.",
            "Completed. [acknowledge-passive-stop]",
        ):
            with self.subTest(message=message):
                self.assert_allowed(
                    self.run_hook(
                        message=message,
                        transcript_entries=[entry("user", "request")],
                    )
                )

    def test_nonpassive_subagent_and_dispatched_review_allow_directly(self) -> None:
        subagent = self.run_hook(
            message="Implementation result.",
            transcript_entries=[entry("user", "request")],
            extra_envelope={"agent_id": "agent-1"},
        )
        self.assert_allowed(subagent)

        dispatched_review = self.run_hook(
            message="Review result.",
            transcript_entries=[entry("user", "request")],
            extra_env={"ORCHESTRARIUM_DISPATCHED_REVIEW": "1"},
        )
        self.assert_allowed(dispatched_review)

    def test_strong_phrase_with_stop_hook_active_allows_stop(self) -> None:
        result = self.run_hook(
            message="Жду ответа бота",
            transcript_entries=[entry("user", "status?")],
            extra_envelope={"stop_hook_active": True},
        )
        self.assert_allowed(result)

    def test_strong_phrase_without_relevant_probe_blocks_stop(self) -> None:
        result = self.run_hook(
            message="Жду ответа бота",
            transcript_entries=[entry("user", "status?")],
        )
        self.assert_passive_blocked(result)

    def test_strong_phrase_from_subagent_allows_stop_without_probe(self) -> None:
        result = self.run_hook(
            message="Жду ответа бота",
            transcript_entries=[entry("user", "status?")],
            extra_envelope={"agent_id": "agent-1"},
        )
        self.assert_allowed(result)

    def test_dispatched_review_env_allows_stop_without_probe(self) -> None:
        result = self.run_hook(
            message="Жду ответа бота",
            transcript_entries=[entry("user", "status?")],
            extra_env={"ORCHESTRARIUM_DISPATCHED_REVIEW": "1"},
        )
        self.assert_allowed(result)

    def test_dispatched_review_policy_is_injected_from_composition_root(self) -> None:
        for script in SCRIPT_PATHS:
            source = script.read_text(encoding="utf-8")
            tree = ast.parse(source)
            functions = {
                node.name: node
                for node in tree.body
                if isinstance(node, ast.FunctionDef)
            }
            with self.subTest(script=script):
                self.assertIn("resolve_runtime_config", functions)
                self.assertIn("main", functions)
                main = functions["main"]
                self.assertEqual([arg.arg for arg in main.args.args], ["config"])
                main_source = ast.get_source_segment(source, main) or ""
                self.assertNotIn("os.environ", main_source)
                self.assertNotIn("os.getenv", main_source)
                self.assertEqual(source.count("os.environ"), 1)
                self.assertIn(
                    "main(resolve_runtime_config(os.environ))",
                    source,
                )

    def test_strong_phrase_with_relevant_bash_date_probe_allows_stop(self) -> None:
        result = self.run_hook(
            message="Жду ответа бота",
            transcript_entries=[entry("user", "status?"), tool_entry("Bash", {"command": "date"})],
        )
        self.assert_allowed(result)

    def test_strong_phrase_with_relevant_gh_pr_probe_allows_stop(self) -> None:
        result = self.run_hook(
            message="Waiting for review",
            transcript_entries=[
                entry("user", "status?"),
                tool_entry("Bash", {"command": "gh pr view 209 --json reviewDecision"}),
            ],
        )
        self.assert_allowed(result)

    def test_strong_phrase_with_relevant_read_output_path_allows_stop(self) -> None:
        result = self.run_hook(
            message="Waiting for bot reply",
            transcript_entries=[
                entry("user", "status?"),
                tool_entry("Read", {"file_path": ".scratch/codex-prompts/passive-stop.out"}),
            ],
        )
        self.assert_allowed(result)

    def test_probe_followed_by_a_real_tool_result_still_allows_stop(self) -> None:
        # BLOCKER regression: `slice_current_turn`'s boundary used to be ANY
        # role=user entry, including a tool_result (Claude Code records tool
        # OUTPUT under role=user). In a real tool-using turn a probe's own
        # tool_result sits AFTER the probe call, so the boundary landed on that
        # trailing tool_result and the "current turn" collapsed to nothing after
        # it -- silently discarding the probe call itself. Every prior test in
        # this file omitted the tool_result entry, which is exactly what masked
        # this: the probe-allowance was DEAD in any real tool-using turn.
        result = self.run_hook(
            message="Waiting for review",
            transcript_entries=[
                entry("user", "status?"),
                tool_entry("Bash", {"command": "gh pr view 209 --json reviewDecision"}),
                tool_result_entry("reviewDecision: null"),
            ],
        )
        self.assert_allowed(result)

    def test_strong_phrase_with_irrelevant_bash_noop_blocks_stop(self) -> None:
        result = self.run_hook(
            message="Жду ответа бота",
            transcript_entries=[entry("user", "status?"), tool_entry("Bash", {"command": "true"})],
        )
        self.assert_passive_blocked(result)

    def test_strong_phrase_with_override_marker_allows_stop(self) -> None:
        result = self.run_hook(
            message="Жду ответа бота [acknowledge-passive-stop]",
            transcript_entries=[entry("user", "status?")],
        )
        self.assert_allowed(result)

    def test_weak_waiting_for_alone_allows_stop(self) -> None:
        result = self.run_hook(
            message="waiting for",
            transcript_entries=[entry("user", "status?")],
        )
        self.assert_allowed(result)

    def test_weak_waiting_for_review_approval_blocks_without_probe(self) -> None:
        result = self.run_hook(
            message="waiting for review approval",
            transcript_entries=[entry("user", "status?")],
        )
        self.assert_passive_blocked(result)

    def test_nonpassive_user_handoff_english_allows_stop(self) -> None:
        result = self.run_hook(
            message="waiting for your response",
            transcript_entries=[entry("user", "status?")],
        )
        self.assert_allowed(result)

    def test_bare_waiting_for_reply_from_bot_blocks_without_probe(self) -> None:
        result = self.run_hook(
            message="waiting for reply from bot",
            transcript_entries=[entry("user", "status?")],
        )
        self.assert_passive_blocked(result)

    def test_nonpassive_user_handoff_russian_allows_stop(self) -> None:
        result = self.run_hook(
            message="жду твоего подтверждения",
            transcript_entries=[entry("user", "status?")],
        )
        self.assert_allowed(result)

    def test_user_handoff_waiting_for_your_review_allows_stop(self) -> None:
        # LOWER/OPTIONAL widening: "waiting for your review" is a legitimate
        # human handoff, distinct from "waiting for [bot/CI] review".
        result = self.run_hook(
            message="waiting for your review",
            transcript_entries=[entry("user", "status?")],
        )
        self.assert_allowed(result)

    def test_bare_waiting_for_review_without_your_still_blocks_without_probe(self) -> None:
        # The widening must stay scoped to "waiting for YOUR review" -- a bare
        # "waiting for review" (no "your") is exactly the ambiguous CI/bot-review
        # phrasing the guard exists to catch and must still block without a probe.
        result = self.run_hook(
            message="waiting for review approval",
            transcript_entries=[entry("user", "status?")],
        )
        self.assert_passive_blocked(result)

    def test_nonpassive_user_handoff_russian_ukazaniy_allows_stop(self) -> None:
        result = self.run_hook(
            message="жду указаний",
            transcript_entries=[entry("user", "status?")],
        )
        self.assert_allowed(result)

    def test_nonpassive_user_handoff_russian_komandy_allows_stop(self) -> None:
        result = self.run_hook(
            message="жду команды",
            transcript_entries=[entry("user", "status?")],
        )
        self.assert_allowed(result)

    def test_nonpassive_user_handoff_russian_otmashki_allows_stop(self) -> None:
        result = self.run_hook(
            message="жду отмашки",
            transcript_entries=[entry("user", "status?")],
        )
        self.assert_allowed(result)

    def test_reported_russian_failure_pattern_blocks_without_probe(self) -> None:
        result = self.run_hook(
            message="жду ответа бота (3-5 мин обычно). Готов итерировать findings когда придёт.",
            transcript_entries=[entry("user", "status?")],
        )
        self.assert_passive_blocked(result)

    def test_malformed_envelope_allows_stop(self) -> None:
        result = self.run_hook(raw_stdin="{not json")
        self.assert_allowed(result)

    def test_missing_last_assistant_message_allows_stop(self) -> None:
        result = self.run_hook(
            message=None,
            transcript_entries=[entry("user", "status?")],
        )
        self.assert_allowed(result)

    def test_empty_last_assistant_message_allows_stop(self) -> None:
        result = self.run_hook(
            message="   ",
            transcript_entries=[entry("user", "status?")],
        )
        self.assert_allowed(result)

    def test_empty_stdin_allows_stop(self) -> None:
        result = self.run_hook(raw_stdin="")
        self.assert_allowed(result)

    def test_current_observed_opaque_time_transport_returns_no_verdict(self) -> None:
        self.assert_allowed(self.run_hook(
            message="Waiting for review", transcript_entries=[
                entry("user", "Check current review state."), *opaque_pair(shell_receipt()),
            ],
        ))

    def test_completed_opaque_transport_returns_no_verdict_for_all_observation_kinds(self) -> None:
        cases = (
            ("job-status", shell_receipt(output='{"status":"failed","job":"synthetic"}')),
            ("log", "ERROR: synthetic job failed; awaiting a retry."),
            ("read", "Review result: changes requested."),
            ("model-context-protocol", {"content": [{"type": "text", "text": "Job failed"}], "isError": False}),
            ("unrelated-opaque-limitation", {"status": "failed", "value": 42}),
        )
        for label, body in cases:
            with self.subTest(observation=label):
                pair = opaque_pair(body, call_id="opaque-" + label,
                                   input_text="// An opaque transport input\ntext(result);")
                self.assert_allowed(self.run_hook(
                    message="Waiting for review", transcript_entries=[entry("user", "Check state."), *pair],
                ))

    def test_opaque_transport_is_indeterminate_not_a_recognized_probe(self) -> None:
        script = SCRIPT_PATHS[0]
        spec = importlib.util.spec_from_file_location("passive_stop_acquisition_test", script)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        sys.path.insert(0, str(script.parent))
        try:
            spec.loader.exec_module(module)
            self.assertIsNone(module._has_relevant_probe(opaque_pair(shell_receipt())))
            self.assertIs(module._has_relevant_probe([tool_entry("Bash", {"command": "date"})]), True)
            self.assertIs(module._has_relevant_probe([tool_entry("Bash", {"command": "true"})]), False)
        finally:
            sys.path.pop(0)
            sys.modules.pop(spec.name, None)

    def test_degraded_opaque_transport_does_not_create_indeterminate_treatment(self) -> None:
        base = opaque_pair(shell_receipt())
        cases: list[tuple[str, list[dict]]] = []

        def changed(label: str, *, call: dict | None = None, result: dict | None = None) -> None:
            pair = copy.deepcopy(base)
            if call:
                pair[0]["payload"].update(call)
            if result:
                pair[1]["payload"].update(result)
            cases.append((label, pair))

        cases.extend((
            ("unpaired-call", base[:1]), ("unpaired-result", base[1:]),
            ("duplicate-call", [base[0], *base]), ("duplicate-result", [*base, base[1]]),
            ("reversed-pair", list(reversed(base))),
            ("prior-turn-call", [base[0], entry("user", "New request."), base[1]]),
        ))
        changed("unmatched-identity", result={"call_id": "different"})
        changed("missing-call-identity", call={"call_id": None})
        changed("empty-identities", call={"call_id": " "}, result={"call_id": " "})
        changed("empty-input", call={"input": " "})
        changed("nonstring-input", call={"input": {"cmd": "Get-Date"}})
        changed("pending-call", call={"status": "in_progress"})
        changed("failed-call", call={"status": "failed"})
        changed("missing-call-completion", call={"status": None})
        changed("unknown-call", call={"name": "unknown"})
        changed("wrong-result-type", result={"type": "unknown_output"})
        changed("missing-result-identity", result={"call_id": None})
        changed("pending-result", result={"status": "in_progress"})
        changed("failed-result", result={"status": "failed"})
        changed("explicit-result-error", result={"is_error": True})
        changed("ambiguous-result-error", result={"is_error": "false"})
        changed("empty-output", result={"output": []})
        changed("nonlist-output", result={"output": "Script completed"})
        for label, blocks in (
            ("malformed-block", [{"type": "input_text", "text": 42}]),
            ("unknown-block", [{"type": "unknown", "text": "Script completed"}]),
            ("pending-frame", [{"type": "input_text", "text": "Script running"}, base[1]["payload"]["output"][1]]),
            ("failed-frame", [{"type": "input_text", "text": "Script failed"}, base[1]["payload"]["output"][1]]),
            ("no-result-body", [base[1]["payload"]["output"][0]]),
        ):
            changed(label, result={"output": blocks})
        for label, receipt in (
            ("shell-failed", shell_receipt(exit_code=1)),
            ("shell-missing-status", {k: v for k, v in shell_receipt().items() if k != "exit_code"}),
            ("shell-string-status", shell_receipt(exit_code="0")),
            ("shell-boolean-status", shell_receipt(exit_code=False)),
            ("shell-null-status", shell_receipt(exit_code=None)),
            ("shell-running-session", shell_receipt(session_id=123)),
            ("shell-malformed-output", shell_receipt(output=42)),
            ("malformed-receipt", '{"exit_code":0,"output":'),
            ("tool-execution-error", {"content": [], "isError": True}),
            ("ambiguous-tool-execution-error", {"content": [], "isError": "false"}),
        ):
            cases.append((label, opaque_pair(receipt)))
        for label, pair in cases:
            with self.subTest(degradation=label):
                self.assert_passive_blocked(self.run_hook(
                    message="Waiting for review", transcript_entries=[entry("user", "Check state."), *pair],
                ))

    def test_direct_function_call_fields_preserve_relevant_invocations(self) -> None:
        for name, arguments, wrapped in (
            ("shell_command", {"command": "Get-Date -Format o"}, True),
            ("exec_command", {"cmd": "gh run list"}, False),
            ("functions.exec_command", {"cmd": "Get-Process"}, True),
            ("Read", {"file_path": "task-output.log"}, True),
            ("read", {"path": "review.log"}, False),
            ("TaskOutput", {}, True),
        ):
            call = {"type": "function_call", "call_id": "direct-1", "name": name,
                    "arguments": json.dumps(arguments)}
            if wrapped:
                call = {"type": "response_item", "payload": call}
            with self.subTest(tool=name, wrapped=wrapped):
                self.assert_allowed(self.run_hook(
                    transcript_entries=[entry("user", "Check state."), call],
                ))

    def test_direct_calls_cannot_credit_descriptions_or_malformed_arguments(self) -> None:
        for name, arguments in (
            ("shell_command", json.dumps({"command": "true", "description": "Get-Date"})),
            ("exec_command", json.dumps({"cmd": "true", "description": "gh pr view"})),
            ("Read", json.dumps({"path": "source.py", "description": "review output log"})),
            ("Bash", '["Get-Date"]'), ("Bash", '{"command":'),
        ):
            with self.subTest(tool=name, arguments=arguments):
                self.assert_passive_blocked(self.run_hook(transcript_entries=[
                    entry("user", "Check state."),
                    {"type": "response_item", "payload": {
                        "type": "function_call", "call_id": "direct-1", "name": name, "arguments": arguments,
                    }},
                ]))

    def test_command_mentions_and_unknown_records_do_not_supply_transport(self) -> None:
        for records in (
            [entry("assistant", "Get-Date; Script completed")],
            [{"type": "unknown", "payload": {"name": "exec", "input": "Get-Date", "status": "completed"}}],
            [entry("user", "Get-Date; Script completed")],
        ):
            with self.subTest(records=records):
                self.assert_passive_blocked(self.run_hook(transcript_entries=[entry("user", "Check state."), *records]))

    def test_malformed_receipt_containers_remain_nonqualifying(self) -> None:
        for label, body in (
            ("malformed-object-control", '{"exit_code":1,"output":'),
            ("valid-failed-array-control", [shell_receipt(exit_code=1)]),
            ("malformed-failed-array", '[{"exit_code":1,"output":'),
            ("malformed-mixed-array", '[{"status":"failed"},{"output":"stopped","exit_code":1'),
            ("unclosed-success-array", '[{"exit_code":0,"output":"complete"}'),
        ):
            with self.subTest(container=label):
                self.assert_passive_blocked(self.run_hook(
                    message="Waiting for review", transcript_entries=[
                        entry("user", "Check state."), *opaque_pair(body),
                    ],
                ))

    def test_nonreceipt_json_key_mentions_remain_opaque_observations(self) -> None:
        for label, body in (
            ("ordinary-bracketed-log", '[ERROR] log mentions the JSON key "exit_code":1 as an example.'),
            ("subject-status-array", [{"status": "failed", "job": "synthetic"}]),
            ("quoted-key-in-subject", {"note": 'The example key "exit_code":1 is not an execution result.'}),
            ("malformed-subject-json", '{"status":"failed","note":'),
        ):
            with self.subTest(observation=label):
                self.assert_allowed(self.run_hook(
                    message="Waiting for review", transcript_entries=[
                        entry("user", "Check state."), *opaque_pair(body),
                    ],
                ))

if __name__ == "__main__":
    unittest.main()
