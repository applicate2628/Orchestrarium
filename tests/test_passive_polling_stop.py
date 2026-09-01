"""Regression tests for passive-polling Stop hook enforcement."""

from __future__ import annotations

import ast
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

    def assert_blocked(self, result: subprocess.CompletedProcess) -> None:
        payload = json.loads(result.stdout)
        self.assertEqual(payload["decision"], "block")
        self.assertIn("passive-polling Stop guard", payload["reason"])

    def test_last_assistant_message_without_polling_phrase_allows_stop(self) -> None:
        result = self.run_hook(
            message="Verification finished; tests are listed below.",
            transcript_entries=[entry("user", "status?")],
        )
        self.assert_allowed(result)

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
        self.assert_blocked(result)

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
        self.assert_blocked(result)

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
        self.assert_blocked(result)

    def test_user_handoff_english_allows_stop(self) -> None:
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
        self.assert_blocked(result)

    def test_user_handoff_russian_allows_stop(self) -> None:
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
        self.assert_blocked(result)

    def test_user_handoff_russian_ukazaniy_allows_stop(self) -> None:
        result = self.run_hook(
            message="жду указаний",
            transcript_entries=[entry("user", "status?")],
        )
        self.assert_allowed(result)

    def test_user_handoff_russian_komandy_allows_stop(self) -> None:
        result = self.run_hook(
            message="жду команды",
            transcript_entries=[entry("user", "status?")],
        )
        self.assert_allowed(result)

    def test_user_handoff_russian_otmashki_allows_stop(self) -> None:
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
        self.assert_blocked(result)

    def test_malformed_envelope_allows_stop(self) -> None:
        result = self.run_hook(raw_stdin="{not json")
        self.assert_allowed(result)

    def test_missing_last_assistant_message_allows_stop(self) -> None:
        result = self.run_hook(
            message=None,
            transcript_entries=[entry("user", "status?")],
        )
        self.assert_allowed(result)

    def test_empty_stdin_allows_stop(self) -> None:
        result = self.run_hook(raw_stdin="")
        self.assert_allowed(result)


if __name__ == "__main__":
    unittest.main()
