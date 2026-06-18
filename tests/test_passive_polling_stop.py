"""Regression tests for passive-polling Stop hook enforcement."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATHS = (
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
