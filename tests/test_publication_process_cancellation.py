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
    async def _cancel_if_requested(self, task, count):
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
                        await self._cancel_if_requested(
                            task, count if window == "acquire" else 1
                        )
                        if window == "acquire":
                            self.assertFalse(task.done(), "acquisition was abandoned")
                        acquire_release.set()
                        self.assertTrue(await asyncio.to_thread(close_started.wait, 2.0))
                        if window == "close":
                            await self._cancel_if_requested(task, count)
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
                            await self._cancel_if_requested(task, count)
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

    def test_process_creation_retains_the_child_until_handoff_or_cancelled_reap(self):
        from asyncio.base_subprocess import BaseSubprocessTransport

        module = _load_canonical_scanner("_scanner_created_child_cancellation")
        prior = _linux_child_subreaper_state()
        real_connect = BaseSubprocessTransport._connect_pipes
        for count, cleanup_complete in ((0, True), (1, True), (3, True), (3, False)):
            with self.subTest(cancellations=count, cleanup_complete=cleanup_complete):
                async def exercise():
                    started, release, connected = asyncio.Event(), asyncio.Event(), asyncio.Event()
                    transports = []
                    returned = []
                    real_settle = module._settle_owned_async_process

                    async def settle_creation(*args, **kwargs):
                        settled = await real_settle(*args, **kwargs)
                        return settled and cleanup_complete

                    async def held_connect(transport, waiter):
                        transports.append(transport)
                        started.set()
                        try:
                            await release.wait()
                            return await real_connect(transport, waiter)
                        finally:
                            connected.set()

                    # Hold the real stdlib pipe connection after its process is created;
                    # replacing create_subprocess_exec itself would not test this handoff.
                    with mock.patch.object(BaseSubprocessTransport, "_connect_pipes", held_connect), \
                         mock.patch.object(module, "_settle_owned_async_process", settle_creation):
                        task = asyncio.create_task(module._create_owned_async_process(
                            (sys.executable, "-c", "import time;time.sleep(60)"),
                            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.DEVNULL,
                        ))
                        try:
                            await asyncio.wait_for(started.wait(), 2.0)
                            await self._cancel_if_requested(task, count)
                            self.assertFalse(task.done(), "created process handoff was abandoned")
                            release.set()
                            if count:
                                if cleanup_complete:
                                    with self.assertRaises(asyncio.CancelledError) as caught:
                                        await task
                                    self.assertEqual(caught.exception.args, ("cancel-0",))
                                else:
                                    with self.assertRaisesRegex(RuntimeError, "creation did not settle"):
                                        await task
                                self.assertIsNotNone(transports[0].get_returncode())
                                self.assertTrue(transports[0]._finished)
                            else:
                                returned.append(await task)
                                self.assertIsNone(returned[0][0].returncode)
                                self.assertTrue(await real_settle(*returned[0]))
                            self.assertTrue(connected.is_set())
                        finally:
                            release.set()
                            if transports:
                                await asyncio.wait_for(connected.wait(), 2.0)
                            outcome = await asyncio.gather(task, return_exceptions=True)
                            if isinstance(outcome[0], tuple) and not returned:
                                self.assertTrue(await real_settle(*outcome[0]))
                            if transports:
                                transports[0].close()
                                await asyncio.wait_for(transports[0]._wait(), 2.0)

                try:
                    asyncio.run(exercise())
                finally:
                    self.assertEqual(_linux_child_subreaper_state(), prior)

    def test_failed_spawn_waits_for_owner_close_before_preserving_the_failure(self):
        module = _load_canonical_scanner("_scanner_failed_spawn_cancellation")
        real_acquire = module.PosixProcessGroupOwnerV1.acquire
        prior = _linux_child_subreaper_state()
        for failure_type in (OSError, asyncio.CancelledError):
            for count in (0, 1, 3):
                with self.subTest(failure=failure_type.__name__, cancellations=count):
                    started, release, done = (
                        threading.Event(), threading.Event(), threading.Event()
                    )
                    closures = []
                    spawn_failure = failure_type("initial spawn failure")

                    class Owner:
                        def __init__(self):
                            self.real_owner = real_acquire()

                        @property
                        def popen_kwargs(self):
                            return self.real_owner.popen_kwargs

                        def close(self):
                            started.set()
                            try:
                                if not release.wait(2.0):
                                    raise TimeoutError("close was not released")
                                closure = self.real_owner.close()
                                closures.append(closure)
                                return closure
                            finally:
                                done.set()

                    async def failed_spawn(*args, **kwargs):
                        raise spawn_failure

                    async def exercise():
                        with mock.patch.object(module.PosixProcessGroupOwnerV1, "acquire", Owner), \
                             mock.patch.object(module.asyncio, "create_subprocess_exec", failed_spawn):
                            task = asyncio.create_task(module._create_owned_async_process(("unused",)))
                            try:
                                self.assertTrue(await asyncio.to_thread(started.wait, 2.0))
                                await self._cancel_if_requested(task, count)
                                self.assertFalse(task.done(), "failed-spawn cleanup was abandoned")
                                release.set()
                                with self.assertRaises(failure_type) as caught:
                                    await task
                                self.assertIs(caught.exception, spawn_failure)
                                self.assertTrue(done.is_set())
                                self.assertEqual(len(closures), 1)
                                self.assertTrue(closures[0].complete)
                            finally:
                                release.set()
                                await asyncio.gather(task, return_exceptions=True)
                                self.assertTrue(await asyncio.to_thread(done.wait, 2.0))

                    try:
                        asyncio.run(exercise())
                    finally:
                        self.assertEqual(_linux_child_subreaper_state(), prior)

    def test_selection_cancellation_settles_child_and_input_after_output_eof(self):
        module = _load_canonical_scanner("_scanner_selection_cancellation")
        prior = _linux_child_subreaper_state()
        cases = [(window, data, False)
                 for window in ("wait", "child", "input")
                 for data in (None, b"synthetic input\n")]
        cases += [(window, b"synthetic input\n", True) for window in ("child", "input")]
        for window, data, fail_read in cases:
            with self.subTest(window=window, stdin=data is not None, fail_read=fail_read):
                async def exercise():
                    created = []
                    waiting, cleaning, release, input_joined = (
                        asyncio.Event(), asyncio.Event(), asyncio.Event(), asyncio.Event()
                    )
                    real_create = module._create_owned_async_process
                    real_wait = module._wait_owned_async_direct
                    real_settle = module._settle_owned_async_process
                    real_join = module._settle_selection_input

                    async def capture_create(*args, **kwargs):
                        result = await real_create(*args, **kwargs)
                        created.append(result)
                        return result

                    async def wait_child(*args, **kwargs):
                        waiting.set()
                        return await real_wait(*args, **kwargs)

                    async def settle_child(*args, **kwargs):
                        if window == "child":
                            cleaning.set()
                            await release.wait()
                        return await real_settle(*args, **kwargs)

                    async def join_input(*args, **kwargs):
                        if window == "input":
                            cleaning.set()
                            await release.wait()
                        result = await real_join(*args, **kwargs)
                        input_joined.set()
                        return result

                    read_failure = module._refusal("PS-MSG-FRAME", "selection-test")
                    with mock.patch.object(module, "_create_owned_async_process", capture_create), \
                         mock.patch.object(module, "_wait_owned_async_direct", wait_child), \
                         mock.patch.object(module, "_settle_owned_async_process", settle_child), \
                         mock.patch.object(module, "_settle_selection_input", join_input):
                        task = asyncio.create_task(module._read_git_lines_bounded(
                            (sys.executable, "-c",
                             "import os,time;os.write(1,b'row\\n');os.close(1);time.sleep(60)"),
                            byte_cap=100, line_cap=100,
                            deadline=asyncio.get_running_loop().time() + 5.0,
                            accepted_codes=frozenset({0}), input_bytes=data,
                            on_line=(lambda row: read_failure) if fail_read else None,
                        ))
                        try:
                            if not fail_read:
                                await asyncio.wait_for(waiting.wait(), 2.0)
                                await self._cancel_if_requested(task, 1)
                            if window != "wait":
                                await asyncio.wait_for(cleaning.wait(), 2.0)
                                await self._cancel_if_requested(task, 3)
                                self.assertFalse(task.done(), "selection cleanup was abandoned")
                            release.set()
                            result = await task
                            if fail_read:
                                self.assertIs(result, read_failure)
                            else:
                                self.assertEqual((result.failure_id, result.reason),
                                                 ("PS-MSG-READ", "cancelled"))
                            self.assertTrue(input_joined.is_set())
                            process, owner, observation = created[0]
                            self.assertIsNotNone(process.returncode)
                            self.assertTrue(observation.task.done())
                            self.assertTrue(process.stdout.at_eof())
                            self.assertTrue(owner.close().complete)
                        finally:
                            release.set()
                            await asyncio.gather(task, return_exceptions=True)
                            if created:
                                self.assertTrue(await real_settle(*created[0]))

                try:
                    asyncio.run(exercise())
                finally:
                    self.assertEqual(_linux_child_subreaper_state(), prior)

    def test_reader_finalization_keeps_ownership_until_the_reap_certificate(self):
        module = _load_canonical_scanner("_scanner_reader_finalize_cancellation")
        prior = _linux_child_subreaper_state()
        for count in (0, 1, 2, 3):
            with self.subTest(cancellations=count):
                async def exercise():
                    reader = module.ObjectReaderSession(
                        argv=(sys.executable, "-c", "import time;time.sleep(60)"),
                        settle_timeout=1.0,
                    )
                    self.assertIsNone(await reader.start())
                    process = reader.process
                    started, release = asyncio.Event(), asyncio.Event()
                    real_wait_closed = process.stdin.wait_closed

                    async def held_wait_closed():
                        started.set()
                        await release.wait()
                        return await real_wait_closed()

                    with mock.patch.object(process.stdin, "wait_closed", held_wait_closed):
                        task = asyncio.create_task(reader.finalize())
                        try:
                            await asyncio.wait_for(started.wait(), 2.0)
                            await self._cancel_if_requested(task, count)
                            self.assertFalse(task.done(), "reader finalization was abandoned")
                            self.assertIsNone(reader.reap_certificate)
                            release.set()
                            result = await task
                            if count:
                                self.assertIsInstance(result, module.Refusal)
                                self.assertEqual((result.failure_id, result.reason),
                                                 ("PS-MSG-READ", "cancelled"))
                            else:
                                self.assertIsNone(result)
                            self.assertIsNotNone(process.returncode)
                            self.assertTrue(reader._direct_observation.task.done())
                            self.assertTrue(process.stdout.at_eof())
                            self.assertTrue(reader.is_finalized)
                            self.assertTrue(reader.reap_certificate.complete)
                            self.assertEqual(reader.reap_certificate.attempts_used, 1)
                        finally:
                            release.set()
                            await asyncio.gather(task, return_exceptions=True)
                            if not reader.is_finalized:
                                # Release owners even when the regression fails on old code.
                                await reader.finalize()

                try:
                    asyncio.run(exercise())
                finally:
                    self.assertEqual(_linux_child_subreaper_state(), prior)


if __name__ == "__main__":
    unittest.main()
