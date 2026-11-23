"""Keep scanner-owned Linux resources through repeated caller cancellation."""

import asyncio
import ctypes
import importlib.util
from pathlib import Path
import sys
import threading
import unittest
from unittest import mock


SCANNER = Path(__file__).resolve().parents[1] / "scripts/universal-hooks/scripts/check-publication-safety.py"


def _load_canonical_scanner(name):
    spec = importlib.util.spec_from_file_location(name, SCANNER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module


def _linux_child_subreaper_state():
    libc = ctypes.CDLL(None, use_errno=True)
    state = ctypes.c_int()
    if libc.prctl(37, ctypes.byref(state), 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "PR_GET_CHILD_SUBREAPER")
    return state.value


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux process-owner cancellation")
class TestPublicationSafetyPosixCancellation(unittest.TestCase):
    async def _cancel_twice_if_requested(self, task, count):
        for attempt in range(count):
            task.cancel(f"cancel-{attempt}")
            # Each cancellation reaches a distinct suspended owner await.
            await asyncio.sleep(0)
            await asyncio.sleep(0)

    def test_acquisition_and_close_keep_the_eventual_owner_until_settled(self):
        module = _load_canonical_scanner("_scanner_posix_acquire_cancellation")
        real_acquire = module.PosixProcessGroupOwnerV1.acquire
        prior = _linux_child_subreaper_state()

        for window, count in (("normal", 0), ("acquire", 1), ("acquire", 2),
                              ("close", 1), ("close", 2), ("close-error", 1)):
            with self.subTest(window=window, count=count):
                acquire_started, acquire_release = threading.Event(), threading.Event()
                close_started, close_release, close_done = (
                    threading.Event(), threading.Event(), threading.Event()
                )
                acquired = []
                closures = []
                close_failure = OSError("synthetic owner close failure")

                class Owner:
                    def close(self):
                        close_started.set()
                        try:
                            if not close_release.wait(2.0):
                                raise TimeoutError("close was not released")
                            closures.append(acquired[0].close())
                            if window == "close-error":
                                raise close_failure
                            return closures[-1]
                        finally:
                            close_done.set()

                proxy = Owner()

                def delayed_acquire():
                    acquire_started.set()
                    if not acquire_release.wait(2.0):
                        raise TimeoutError("acquisition was not released")
                    acquired.append(real_acquire())
                    return proxy

                async def exercise():
                    task = asyncio.create_task(module._acquire_posix_process_group_owner())
                    try:
                        self.assertTrue(await asyncio.to_thread(acquire_started.wait, 2.0))
                        if window == "normal":
                            acquire_release.set()
                            owner = await task
                            self.assertIs(owner, proxy)
                            self.assertFalse(close_started.is_set())
                            close_release.set()
                            self.assertTrue((await asyncio.to_thread(owner.close)).complete)
                            return
                        await self._cancel_twice_if_requested(
                            task, count if window == "acquire" else 1
                        )
                        if window == "acquire":
                            self.assertFalse(task.done(), "acquisition was abandoned")
                        acquire_release.set()
                        self.assertTrue(await asyncio.to_thread(close_started.wait, 2.0))
                        if window == "close":
                            await self._cancel_twice_if_requested(task, count)
                            self.assertFalse(task.done(), "close was abandoned")
                        close_release.set()
                        if window == "close-error":
                            with self.assertRaises(OSError) as caught:
                                await task
                            self.assertIs(caught.exception, close_failure)
                        else:
                            with self.assertRaises(asyncio.CancelledError) as caught:
                                await task
                            self.assertEqual(caught.exception.args, ("cancel-0",))
                        self.assertTrue(close_done.is_set())
                        self.assertEqual(len(closures), 1)
                        self.assertTrue(closures[0].complete)
                    finally:
                        acquire_release.set()
                        close_release.set()
                        await asyncio.gather(task, return_exceptions=True)

                try:
                    with mock.patch.object(module.PosixProcessGroupOwnerV1, "acquire",
                                           side_effect=delayed_acquire):
                        asyncio.run(exercise())
                finally:
                    # Failed assertions must not strand the real process-wide owner.
                    acquire_release.set()
                    close_release.set()
                    for owner in acquired:
                        owner.close()
                self.assertEqual(_linux_child_subreaper_state(), prior)

    def test_settlement_waits_for_child_reap_and_pipe_drain_after_cancellation(self):
        module = _load_canonical_scanner("_scanner_posix_settle_cancellation")
        prior = _linux_child_subreaper_state()
        for count in (0, 1, 2):
            with self.subTest(cancellations=count):
                started, release, settled = threading.Event(), threading.Event(), threading.Event()
                closures = []

                async def exercise():
                    process, owner, observation = await module._create_owned_async_process(
                        (sys.executable, "-c", "import time;time.sleep(60)"),
                        stdin=asyncio.subprocess.DEVNULL,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    real_settle = owner.settle

                    def delayed_settle(*args, **kwargs):
                        started.set()
                        try:
                            if not release.wait(2.0):
                                raise TimeoutError("settlement was not released")
                            closure = real_settle(*args, **kwargs)
                            closures.append(closure)
                            return closure
                        finally:
                            settled.set()

                    with mock.patch.object(owner, "settle", side_effect=delayed_settle):
                        task = asyncio.create_task(module._settle_owned_async_process(
                            process, owner, observation, timeout_seconds=1.0,
                            drain_readers=(process.stdout, process.stderr),
                        ))
                        try:
                            self.assertTrue(await asyncio.to_thread(started.wait, 2.0))
                            await self._cancel_twice_if_requested(task, count)
                            self.assertFalse(task.done(), "settlement was abandoned")
                            release.set()
                            if count:
                                with self.assertRaises(asyncio.CancelledError) as caught:
                                    await task
                                self.assertEqual(caught.exception.args, ("cancel-0",))
                            else:
                                self.assertTrue(await task)
                            self.assertTrue(settled.is_set())
                            self.assertEqual(len(closures), 1)
                            self.assertTrue(closures[0].complete)
                            self.assertTrue(observation.task.done())
                            self.assertEqual(process.returncode, observation.poll())
                            self.assertTrue(process.stdout.at_eof())
                            self.assertTrue(process.stderr.at_eof())
                        finally:
                            release.set()
                            await asyncio.gather(task, return_exceptions=True)
                            self.assertTrue(await asyncio.to_thread(settled.wait, 2.0))
                            await asyncio.to_thread(real_settle, 1.0,
                                                    direct_process=observation)
                            await process.stdout.read()
                            await process.stderr.read()

                asyncio.run(exercise())
                self.assertEqual(_linux_child_subreaper_state(), prior)


if __name__ == "__main__":
    unittest.main()
