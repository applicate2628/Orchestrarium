"""Worker cleanup ownership under cancellation; no provider or process launches."""
import asyncio
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from sdk_execution.contracts import CancelReceipt, ExecutionRequest, ExecutionResult
from sdk_execution.worker import decode_frame, serve_operation


class WorkerCancellationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.request = ExecutionRequest(
            provider="codex", work_item_id="worker-fixture",
            external_dispatch_id="dispatch-fixture", external_evidence_run_id="evidence-fixture",
            artifact_id="review-fixture", role="architecture-reviewer", model="model-fixture",
            effort="high", cwd=str(Path(__file__).resolve().parents[1]),
            account_binding="account-fixture", prompt="fixture",
            coordinator_binding="coordinator-fixture", scope=("scripts/sdk_execution",),
        )

    async def check_cleanup(self, pause_at, *, control_error=None):
        started, paused, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
        executed, cancellations, writes, output = [], [], [], []

        async def pause(stage):
            if stage == pause_at:
                paused.set()
                await release.wait()

        class Adapter:
            async def execute(self, request):
                executed.append(asyncio.current_task())
                started.set()
                try:
                    await asyncio.Future()
                except asyncio.CancelledError:
                    return ExecutionResult(request, "interrupted")

            async def cancel(self, run_id):
                await pause("cancel")
                cancellations.append(run_id)
                return CancelReceipt(run_id, True, False)

        async def read():
            try:
                if control_error is not None:
                    await started.wait()
                    raise control_error
                await asyncio.Future()
            finally:
                await pause("control")

        async def write(payload):
            writes.append(payload)
            await pause("terminal")
            output.append(decode_frame(payload))

        operation = asyncio.create_task(serve_operation(self.request, Adapter(), read, write))
        try:
            await asyncio.wait_for(started.wait(), 2)
            if control_error is None:
                operation.cancel()
            await asyncio.wait_for(paused.wait(), 2)
            operation.cancel()
            await asyncio.sleep(0)
            operation.cancel()
            release.set()
            if control_error is None:
                with self.assertRaises(asyncio.CancelledError):
                    await operation
            else:
                with self.assertRaises(type(control_error)) as caught:
                    await operation
                self.assertIs(caught.exception, control_error)
            self.assertTrue(executed[0].done(), "worker returned with active execution")
            self.assertEqual(cancellations, [self.request.run_id])
            self.assertEqual(len(writes), 1, "terminal write must not be retried")
            self.assertEqual([frame["kind"] for frame in output], ["result"])
            self.assertEqual(output[0]["result"]["status"], "interrupted")
        finally:
            release.set()
            for task in executed:
                if not task.done():
                    task.cancel()
            await asyncio.gather(operation, *executed, return_exceptions=True)

    async def test_repeated_cancellation_during_control_cleanup(self):
        await self.check_cleanup("control")

    async def test_repeated_cancellation_during_provider_cancel(self):
        await self.check_cleanup("cancel")

    async def test_repeated_cancellation_during_terminal_write(self):
        await self.check_cleanup("terminal")

    async def test_protocol_failure_survives_cancellation_during_cleanup(self):
        await self.check_cleanup("cancel", control_error=ValueError("fixture control failure"))

    async def test_cancellation_first_received_during_cleanup_still_propagates(self):
        paused, release = asyncio.Event(), asyncio.Event()
        writes = []

        class Adapter:
            async def execute(self, request):
                return ExecutionResult(request, "interrupted")

        async def read():
            try:
                await asyncio.Future()
            finally:
                paused.set()
                await release.wait()

        async def write(payload):
            writes.append(decode_frame(payload))

        operation = asyncio.create_task(serve_operation(self.request, Adapter(), read, write))
        try:
            await asyncio.wait_for(paused.wait(), 2)
            operation.cancel()
            await asyncio.sleep(0)
            operation.cancel()
            release.set()
            with self.assertRaises(asyncio.CancelledError):
                await operation
            self.assertEqual([frame["kind"] for frame in writes], ["result"])
        finally:
            release.set()
            await asyncio.gather(operation, return_exceptions=True)


if __name__ == "__main__":
    unittest.main()
