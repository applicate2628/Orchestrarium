"""Exercise both ends of Copilot worker transport with a synthetic process."""
from functools import partial
import hashlib
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import provider_prompt
from process_supervision.process_runner import EnvironmentRowV1, ProcessRunnerV1
from process_supervision.sdk_worker import run_sdk_worker
from sdk_execution import copilot, receiving, runtime
from sdk_execution.contracts import ExecutionRequest, json_text
from sdk_execution.worker import decode_frame
from _sdk_copilot_support import FakeSdk, payload, simulate_worker_process


class CopilotTransportTests(unittest.TestCase):
    def setUp(self):
        # Use an existing file for executable custody. The synthetic process never runs it.
        executable = Path(copilot.__file__).resolve()
        root = executable.parents[2]
        self.request = ExecutionRequest(
            provider="copilot", work_item_id=root.name, external_dispatch_id="dispatch",
            external_evidence_run_id="evidence", artifact_id="advice.json", role="consultant",
            model="selected-model", effort="high", cwd=str(root), account_binding="selected-context",
            prompt="Analyze supplied context only.", coordinator_binding="root-lead", scope=("advice",),
            result_kind="task", tool_profile="prompt-only", max_events=3)
        self.selection = copilot.CopilotRuntimeSelection(
            str(executable), hashlib.sha256(executable.read_bytes()).hexdigest(),
            str(root), "copilot-explicit-token", provider_prompt.assemble_external_prompt(b"").decode(),
            str(root), None, None, 128 * 1024 * 1024, 10, 10, expected_launch_sha256="a" * 64)
        self.sdk = FakeSdk()
        self.credential = "fixture-" + "private-transport-credential"
        self.frames = []

    def run_worker(self):
        peer = partial(simulate_worker_process, requests=[], output_frames=self.frames)
        # Ledger and native process boundaries are the only substituted owners.
        with ProcessRunnerV1() as process, patch.object(process, "run", peer), \
             patch.object(runtime, "assert_current_launch"), patch.object(copilot, "_load_sdk", return_value=self.sdk):
            return run_sdk_worker(process, self.request,
                environment=(EnvironmentRowV1("COPILOT_GITHUB_TOKEN", self.credential),),
                deadline_monotonic=time.monotonic() + 20,
                job_memory_limit_bytes=self.selection.job_memory_limit_bytes,
                runtime_selection=self.selection.to_dict(), authority=lambda request, effect: None)

    def test_worker_stream_and_terminal_agree_at_parent_receiving(self):
        self.sdk.events = [
            SimpleNamespace(type="assistant.message_delta", data=SimpleNamespace(delta_content="Draft advice.")),
            SimpleNamespace(type="assistant.message", data=SimpleNamespace(content=self.sdk.content)),
        ]
        observed = self.run_worker()
        self.assertIsNone(observed.protocol_error)
        self.assertEqual(observed.observations, observed.result.observations)
        self.assertEqual([row.sequence for row in observed.observations], [0, 1])
        frames = [decode_frame(raw)["kind"] for raw in self.frames]
        self.assertEqual(frames[-3:], ["observation", "observation", "result"])
        self.assertEqual(self.sdk.calls[-3:], ["unsubscribe", "disconnect", "stop"])
        terminal = receiving.terminal_payload(self.request, observed,
            output_context=provider_prompt.ProviderOutputContext((self.credential.encode(),)),
            admitted_sdk_execution=runtime.selected_sdk_execution(self.request, self.selection))
        self.assertEqual(terminal["status"], "completed")
        self.assertFalse(terminal["authorizing"])

    def test_unsafe_content_cannot_reach_observation_frames(self):
        self.sdk.content = json_text(payload(content=self.credential))
        with self.assertRaisesRegex(copilot.CopilotError, "CREDENTIAL_ECHO"):
            self.run_worker()
        self.assertTrue(self.frames)
        self.assertTrue(all(decode_frame(raw)["kind"] == "authority_request" for raw in self.frames))
        self.assertTrue(all(self.credential.encode() not in raw for raw in self.frames))
        self.assertEqual(self.sdk.calls[-3:], ["unsubscribe", "disconnect", "stop"])


if __name__ == "__main__":
    unittest.main()
