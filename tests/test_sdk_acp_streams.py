"""Owned byte facade tests; no provider, subprocess, socket or model calls."""
import asyncio
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from process_supervision import process_runner as owner


def channel_fixture():
    lines = owner._DialogueLineRouterV1()
    channel = owner.ProcessDialogueChannelV1(-1, lines, SimpleNamespace(cancelled=False), time.monotonic()+3, None)
    return channel, lines


def test_owner_stop_wakes_blocked_read_without_eof_or_descriptor_close():
    channel, lines = channel_fixture()
    entered, exited = threading.Event(), threading.Event()
    class ObservedCondition(threading.Condition):
        def wait(self, timeout=None):
            entered.set()
            return super().wait(timeout)
    lines._condition = ObservedCondition()
    errors=[]
    def read():
        try: channel.read_line()
        except BaseException as exc: errors.append(exc)
        finally: exited.set()
    thread=threading.Thread(target=read)
    thread.start()
    try:
        assert entered.wait(1)
        channel.stop_reads()
        assert exited.wait(1)
        assert len(errors)==1 and isinstance(errors[0], owner.DialogueReadStoppedV1)
        assert not isinstance(errors[0], EOFError)
        assert not lines._eof
    finally:
        lines.finish()
        thread.join(4)
        assert not thread.is_alive()


def test_facade_cancelled_blocking_read_drained_before_loop_shutdown():
    from sdk_execution.acp_streams import OwnedAcpStreams
    channel, lines = channel_fixture()
    entered = threading.Event()
    original = channel.read_line
    def read_line():
        entered.set()
        return original()
    channel.read_line = read_line
    async def scenario():
        streams=OwnedAcpStreams(channel,max_buffer_bytes=128)
        read=asyncio.create_task(streams.readuntil())
        assert await asyncio.to_thread(entered.wait, 1)
        read.cancel()
        with pytest.raises(asyncio.CancelledError): await read
        await streams.close()
        assert streams.closed and not lines._eof
    asyncio.run(scenario())


def test_normal_eof_is_not_local_stop():
    from sdk_execution.acp_streams import OwnedAcpStreams
    channel,lines=channel_fixture()
    lines.feed(b'hello\n');lines.finish()
    async def scenario():
        streams=OwnedAcpStreams(channel,max_buffer_bytes=128)
        assert await streams.readuntil()==b'hello\n'
        with pytest.raises(asyncio.IncompleteReadError) as caught: await streams.readuntil()
        assert caught.value.partial == b''
        await streams.close()
    asyncio.run(scenario())


def test_stop_preserves_queued_bytes_and_does_not_change_other_reader():
    a,first=channel_fixture();b,second=channel_fixture()
    first.feed(b'queued\n');second.feed(b'other\n')
    a.stop_reads();first.feed(b'later\n')
    with pytest.raises(owner.DialogueReadStoppedV1):a.read_line()
    assert first._queued_bytes==len(b'queued\n')
    assert b.read_line()==b'other\n'


@pytest.mark.parametrize('kind',['cancel','deadline','failure'])
def test_unstopped_owner_legacy_failures(kind):
    channel,lines=channel_fixture()
    if kind=='cancel': channel._lifecycle.cancelled=True
    elif kind=='deadline': channel._deadline=time.monotonic()-1
    else: lines.finish(failed=True)
    with pytest.raises(owner.ProcessSupervisionError) as caught:channel.read_line()
    assert caught.value.failure_id == {'cancel':'PSV1-CANCELLED','deadline':'PSV1-DEADLINE','failure':'PSV1-KIMI-ACP-PROTOCOL'}[kind]


def test_byte_writer_bounds_short_write_and_error_retention():
    from sdk_execution.acp_streams import OwnedAcpStreams,AcpStreamError
    class Channel:
        def read_line(self):raise EOFError
        def stop_reads(self):pass
        def write_line(self,data):return len(data)-1
    async def scenario():
        streams=OwnedAcpStreams(Channel(),max_buffer_bytes=8)
        with pytest.raises(AcpStreamError,match='write_limit'):streams.write(b'123456789')
        await streams.close()
        streams=OwnedAcpStreams(Channel(),max_buffer_bytes=8)
        streams.write(b'abc\n')
        with pytest.raises(AcpStreamError,match='short_write'):await streams.drain()
        with pytest.raises(AcpStreamError,match='short_write'):await streams.close()
    asyncio.run(scenario())


def test_close_idempotence_write_after_close_and_concurrent_read():
    from sdk_execution.acp_streams import OwnedAcpStreams,AcpStreamError
    channel,lines=channel_fixture()
    async def scenario():
        streams=OwnedAcpStreams(channel,max_buffer_bytes=128)
        pending=asyncio.create_task(streams.readuntil())
        await asyncio.sleep(0)
        with pytest.raises(AcpStreamError,match='concurrent'):await streams.readuntil()
        await streams.close()
        with pytest.raises(owner.DialogueReadStoppedV1):await pending
        await streams.close()
        with pytest.raises(AcpStreamError,match='closed'):streams.write(b'late\n')
        with pytest.raises(AcpStreamError,match='closed'):await streams.readuntil()
    asyncio.run(scenario())


def test_cancelled_stalled_write_retained_and_first_failure_repeated():
    from sdk_execution.acp_streams import OwnedAcpStreams,AcpStreamError
    entered,release=threading.Event(),threading.Event()
    class Channel:
        def read_line(self):raise EOFError
        def stop_reads(self):pass
        def write_line(self,data):
            entered.set()
            assert release.wait(2)
            raise OSError('fixture-write-error')
    async def scenario():
        streams=OwnedAcpStreams(Channel(),max_buffer_bytes=128)
        streams.write(b'hello\n')
        task=asyncio.create_task(streams.drain())
        try:
            assert await asyncio.to_thread(entered.wait,1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):await task
            with pytest.raises(AcpStreamError,match='pending'):streams.write(b'other\n')
            closer=asyncio.create_task(streams.close())
            await asyncio.sleep(0);closer.cancel();await asyncio.sleep(0);closer.cancel()
            assert not closer.done()
            release.set()
            with pytest.raises(OSError,match='fixture-write-error') as first:await closer
            with pytest.raises(OSError) as second:await streams.close()
            assert second.value is first.value
            assert streams.closed
        finally:
            release.set()
            await asyncio.gather(task,return_exceptions=True)
    asyncio.run(scenario())


def test_bounded_read_and_exact_byte_semantics():
    from sdk_execution.acp_streams import OwnedAcpStreams,AcpStreamError
    channel,lines=channel_fixture();lines.feed(b'ab\ncd\n');lines.finish()
    async def scenario():
        streams=OwnedAcpStreams(channel,max_buffer_bytes=16)
        assert await streams.readexactly(2)==b'ab'
        assert await streams.readuntil()==b'\n'
        with pytest.raises(asyncio.IncompleteReadError) as caught:await streams.readexactly(5)
        assert caught.value.partial==b'cd\n' and caught.value.expected==5
        await streams.close()
        other,queue=channel_fixture();queue.feed(b'overlarge\n')
        bounded=OwnedAcpStreams(other,max_buffer_bytes=4)
        with pytest.raises(AcpStreamError,match='read_limit'):await bounded.readuntil()
        with pytest.raises(AcpStreamError,match='read_limit'):await bounded.close()
    asyncio.run(scenario())


def test_owner_raw_capture_continues_after_dialogue_stop(monkeypatch):
    channel,lines=channel_fixture();channel.stop_reads()
    chunks=iter([b'after-stop\n',b''])
    monkeypatch.setattr(owner.os,'read',lambda fd,size:next(chunks))
    captured=[]
    sink=SimpleNamespace(feed=lambda stream,data:captured.append((stream,data)))
    issues=[]
    owner._reader_fd(-1,'stdout',sink,128,issues,SimpleNamespace(close_resource=lambda *a:True),'stdout-fixture',lines)
    assert captured==[('stdout',b'after-stop\n')] and issues==[]
    with pytest.raises(owner.DialogueReadStoppedV1):channel.read_line()


@pytest.mark.parametrize('callback_error',[False,True])
def test_official_acp_connection_byte_facades_initialize_close(callback_error):
    pytest.importorskip('acp',reason='optional official ACP SDK is not installed')
    from acp.core import Connection
    from sdk_execution.acp_streams import OwnedAcpStreams
    first,first_lines=channel_fixture();second,second_lines=channel_fixture()
    # Synthetic owner channels forward bytes; official SDK creates/parses JSON.
    captures=[]
    def forward(lines,data):
        captures.append(data);lines.feed(data);return len(data)
    first.write_line=lambda data:forward(second_lines,data)
    second.write_line=lambda data:forward(first_lines,data)
    async def scenario():
        left,right=OwnedAcpStreams(first,max_buffer_bytes=4096),OwnedAcpStreams(second,max_buffer_bytes=4096)
        async def client(method,params,notification):
            if callback_error:raise ValueError('fixture callback failure')
            return {'accepted':True}
        peer=None
        async def agent(method,params,notification):
            if callback_error:
                await peer.send_request('fixture/callback',{})
            return {'protocolVersion':1}
        local=Connection(client,left,left)
        peer=Connection(agent,right,right)
        try:
            if callback_error:
                with pytest.raises(Exception):await asyncio.wait_for(local.send_request('initialize',{}),2)
            else:
                assert await asyncio.wait_for(local.send_request('initialize',{}),2)=={'protocolVersion':1}
        finally:
            # Required order: SDK close cancels awaiters, then byte facade wakes
            # and drains their synchronous operations before asyncio.run exits.
            await local.close();await left.close()
            await peer.close();await right.close()
        assert left.closed and right.closed
        assert not first_lines._eof and not second_lines._eof
    asyncio.run(scenario())
    assert captures


def test_completed_io_not_accumulated_and_undrained_write_reported():
    from sdk_execution.acp_streams import OwnedAcpStreams,AcpStreamError
    channel,lines=channel_fixture()
    channel.write_line=lambda data:len(data)
    async def scenario():
        streams=OwnedAcpStreams(channel,max_buffer_bytes=16)
        for _ in range(30):
            lines.feed(b'x\n')
            assert await streams.readuntil()==b'x\n'
            streams.write(b'y\n');await streams.drain()
            assert streams._read_task is None and streams._write_task is None
        streams.write(b'unflushed')
        with pytest.raises(AcpStreamError,match='undrained_write'):await streams.close()
        with pytest.raises(AcpStreamError,match='undrained_write'):await streams.close()
    asyncio.run(scenario())


def test_local_stop_does_not_mask_preexisting_owner_failure():
    channel, lines = channel_fixture()
    lines.finish(failed=True)
    with pytest.raises(owner.ProcessSupervisionError) as caught:
        channel.stop_reads()
        channel.read_line()
    assert caught.value.failure_id == 'PSV1-KIMI-ACP-PROTOCOL'


def test_close_retains_owner_failure_after_cancelled_read():
    from sdk_execution.acp_streams import OwnedAcpStreams
    channel, lines = channel_fixture()
    entered, release = threading.Event(), threading.Event()
    original_read, original_stop = channel.read_line, channel.stop_reads
    def read():
        entered.set()
        assert release.wait(2)
        return original_read()
    def stop():
        try:
            original_stop()
        finally:
            release.set()
    channel.read_line, channel.stop_reads = read, stop
    async def scenario():
        streams = OwnedAcpStreams(channel, max_buffer_bytes=128)
        pending = asyncio.create_task(streams.readuntil())
        try:
            assert await asyncio.to_thread(entered.wait, 1)
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
            lines.finish(failed=True)
            with pytest.raises(owner.ProcessSupervisionError) as first:
                await streams.close()
            with pytest.raises(owner.ProcessSupervisionError) as repeated:
                await streams.close()
            assert repeated.value is first.value
            assert streams.closed
        finally:
            release.set()
            await asyncio.gather(pending, return_exceptions=True)
    asyncio.run(scenario())


def test_close_reports_preexisting_owner_failure_without_pending_read():
    from sdk_execution.acp_streams import OwnedAcpStreams
    channel, lines = channel_fixture()
    lines.finish(failed=True)
    async def scenario():
        streams = OwnedAcpStreams(channel, max_buffer_bytes=128)
        with pytest.raises(owner.ProcessSupervisionError) as first:
            await streams.close()
        with pytest.raises(owner.ProcessSupervisionError) as second:
            await streams.close()
        assert second.value is first.value
        assert streams.closed
    asyncio.run(scenario())
