"""Exercise both ends of Copilot worker transport with a synthetic process."""
import asyncio
from functools import partial
import hashlib
import json
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
from sdk_execution.worker import ObservationSink, decode_frame, serve_operation
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

    def run_worker(self, authority=None):
        peer = partial(simulate_worker_process, requests=[], output_frames=self.frames)
        # Ledger and native process boundaries are the only substituted owners.
        with ProcessRunnerV1() as process, patch.object(process, "run", peer), \
             patch.object(runtime, "assert_current_launch"), patch.object(copilot, "_load_sdk", return_value=self.sdk):
            return run_sdk_worker(process, self.request,
                environment=(EnvironmentRowV1("COPILOT_GITHUB_TOKEN", self.credential),),
                deadline_monotonic=time.monotonic() + 20,
                job_memory_limit_bytes=self.selection.job_memory_limit_bytes,
                runtime_selection=self.selection.to_dict(),
                authority=authority or (lambda request, effect: None))

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
        self.assertEqual(frames[-1], "result")
        self.assertEqual(frames.count("observation"), len(observed.observations))
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

    def test_acquired_observations_survive_final_authority_denial(self):
        def authority(request, effect):
            if effect == "copilot_result":
                raise PermissionError("fixture permission was revoked")

        with self.assertRaisesRegex(copilot.CopilotError, "copilot_authority_denied"):
            self.run_worker(authority)
        frames = [decode_frame(raw) for raw in self.frames]
        observations = [frame["observation"] for frame in frames if frame["kind"] == "observation"]
        self.assertEqual(len(observations), 1)
        self.assertIn("Bounded advice.", observations[0]["payload_json"])
        self.assertNotIn("result", [frame["kind"] for frame in frames])
        self.assertEqual(self.sdk.calls[-3:], ["unsubscribe", "disconnect", "stop"])

    def test_acquired_observations_precede_native_cleanup(self):
        before_cleanup = []
        disconnect = self.sdk.disconnect

        async def observe_cleanup():
            before_cleanup.extend(decode_frame(raw) for raw in self.frames
                                  if decode_frame(raw)["kind"] == "observation")
            await disconnect()

        self.sdk.disconnect = observe_cleanup
        observed = self.run_worker()
        self.assertEqual(observed.result.status, "completed")
        self.assertEqual([frame["observation"] for frame in before_cleanup],
                         [value.to_dict() for value in observed.observations])

    def test_new_observation_during_abort_extends_the_captured_batch(self):
        self.sdk.failure = "send"
        self.sdk.events = [SimpleNamespace(type="assistant.message_delta",
            data=SimpleNamespace(delta_content="Before interruption."))]

        async def abort():
            self.sdk.calls.append("abort")
            self.sdk.handler(SimpleNamespace(type="assistant.message_delta",
                data=SimpleNamespace(delta_content="Acquired during interruption.")))

        self.sdk.abort = abort
        observed = self.run_worker()
        self.assertEqual(observed.result.status, "incomplete")
        self.assertEqual(observed.result.execution_error, "copilot_sdk_failed")
        self.assertIsNone(observed.protocol_error)
        self.assertEqual(observed.observations, observed.result.observations)
        self.assertEqual([value.sequence for value in observed.observations], [0, 1])
        self.assertEqual(self.sdk.calls.count("abort"), 1)

    def test_split_credential_deltas_are_not_released_before_full_message_scan(self):
        async def emit_chunks():
            split = len(self.credential) // 2
            for chunk in (self.credential[:split], self.credential[split:]):
                self.sdk.handler(SimpleNamespace(type="assistant.message_delta",
                    data=SimpleNamespace(delta_content=chunk)))
                await asyncio.sleep(0)

        self.sdk.on_send = emit_chunks
        self.sdk.content = json_text(payload(content=self.credential))
        with self.assertRaisesRegex(copilot.CopilotError, "CREDENTIAL_ECHO"):
            self.run_worker()
        content = "".join(json.loads(frame["observation"]["payload_json"])["content"]
            for raw in self.frames if (frame := decode_frame(raw))["kind"] == "observation")
        self.assertNotIn(self.credential, content)

    def test_split_only_credential_deltas_are_refused_in_every_export_path(self):
        for during_abort in (False, True):
            for use_sink in (False, True):
                with self.subTest(during_abort=during_abort, use_sink=use_sink):
                    self.sdk, self.frames = FakeSdk(), []
                    self.sdk.failure = "send"
                    split = len(self.credential) // 2
                    chunks = [SimpleNamespace(type="assistant.message_delta",
                        data=SimpleNamespace(delta_content=value))
                        for value in (self.credential[:split], self.credential[split:])]
                    self.sdk.events = chunks[:1] if during_abort else chunks

                    async def abort():
                        self.sdk.calls.append("abort")
                        if during_abort:
                            self.sdk.handler(chunks[1])

                    self.sdk.abort = abort
                    error = result = None
                    try:
                        result = (self.run_worker().result if use_sink
                                  else asyncio.run(self.executor(None).execute(self.request)))
                    except copilot.CopilotError as exc:
                        error = str(exc)
                    exported = [frame["observation"] for raw in self.frames
                        if (frame := decode_frame(raw))["kind"] == "observation"]
                    if result is not None:
                        exported.extend(value.to_dict() for value in result.observations)
                    content = "".join(json.loads(value["payload_json"])["content"]
                                      for value in exported)
                    self.assertNotIn(self.credential, content)
                    self.assertEqual(error, "E_EXTERNAL_PROVIDER_CREDENTIAL_ECHO")
                    self.assertEqual([value["sequence"] for value in exported],
                                     [0] if use_sink and during_abort else [])
                    self.assertEqual(self.sdk.calls.count("disconnect"), 1)
                    self.assertEqual(self.sdk.calls.count("stop"), 1)

    def executor(self, record):
        return copilot.CopilotExecutor(
            runtime_path=self.selection.executable, base_directory=self.selection.base_directory,
            environment={}, github_token=self.credential,
            assert_current=lambda request, effect: None,
            output_context=provider_prompt.ProviderOutputContext(()),
            timeout_seconds=10, cleanup_timeout_seconds=10, sdk=self.sdk,
            instructions=self.selection.instructions, record=record)

    def test_sink_failure_is_not_retried_and_still_closes_native_owners(self):
        for failure, expected in ((OSError("private sink failure"), "copilot_evidence_sink_failed"),
                                  (asyncio.CancelledError(), "copilot_evidence_sink_cancelled")):
            with self.subTest(failure=type(failure).__name__):
                self.sdk = FakeSdk()
                self.sdk.events = [SimpleNamespace(type="assistant.message_delta",
                    data=SimpleNamespace(delta_content="Acquired advice."))]
                writes = []

                async def refuse(observation):
                    writes.append(observation)
                    if observation.sequence == 1:
                        raise failure

                adapter = self.executor(refuse)
                result = asyncio.run(adapter.execute(self.request))
                self.assertEqual([value.sequence for value in writes], [0, 1])
                self.assertEqual(result.capture_error, expected)
                self.assertEqual(result.status, "incomplete")
                self.assertTrue(result.protocol_closed)
                self.assertIn("Bounded advice.", result.observations[1].payload_json)
                self.assertNotIn("private sink failure", json_text(result.to_dict()))
                self.assertEqual(self.sdk.calls.count("disconnect"), 1)
                self.assertEqual(self.sdk.calls.count("stop"), 1)

    def test_repeated_cancellation_during_cleanup_keeps_stream_and_no_late_abort(self):
        async def scenario():
            entered, release, abort_release = asyncio.Event(), asyncio.Event(), asyncio.Event()

            async def disconnect():
                self.sdk.calls.append("disconnect")
                entered.set()
                await release.wait()

            async def abort():
                self.sdk.calls.append("abort")
                await abort_release.wait()

            async def write(frame):
                self.frames.append(frame)

            async def read():
                await asyncio.Future()

            self.sdk.disconnect, self.sdk.abort = disconnect, abort
            sink = ObservationSink(self.request, SimpleNamespace(write=write))
            adapter = self.executor(sink.record)
            operation = asyncio.create_task(serve_operation(self.request, adapter, read, write))
            try:
                await asyncio.wait_for(entered.wait(), 2)
                operation.cancel()
                await asyncio.sleep(0)
                operation.cancel()
                await asyncio.sleep(0)
                release.set()
                with self.assertRaises(asyncio.CancelledError):
                    await operation
                frames = [decode_frame(raw) for raw in self.frames]
                self.assertEqual([frame["kind"] for frame in frames], ["observation", "result"])
                self.assertEqual(frames[-1]["result"]["status"], "interrupted")
                self.assertIsNone(adapter._abort_task, "teardown created an undrained abort owner")
                self.assertEqual(self.sdk.calls.count("disconnect"), 1)
                self.assertEqual(self.sdk.calls.count("stop"), 1)
            finally:
                release.set()
                abort_release.set()
                await asyncio.gather(operation, return_exceptions=True)
                if adapter._abort_task is not None:
                    await adapter._abort_task

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
