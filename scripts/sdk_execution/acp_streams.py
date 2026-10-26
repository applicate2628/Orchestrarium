"""Bounded byte facade over the existing process owner's dialogue channel.

Pass this object as writer AND reader to public acp.core.Connection. Official
ACP retains JSON/framing/correlation. No descriptor, subprocess or capture owner
is introduced. Close Connection first, then explicitly await facade.close() in
finally BEFORE leaving the asyncio loop. ACP does not close the supplied writer.
Local read stop is not provider EOF; no facade result proves process settlement.
"""
from __future__ import annotations

import asyncio
import inspect
from process_supervision.process_runner import DialogueReadStoppedV1, MAX_STDIN_BYTES
from ._async import drain_owned


class AcpStreamError(ValueError):
    """Stable byte bridge failure, not a provider protocol result."""


class OwnedAcpStreams:
    """Single reader/writer, LF-delimited byte subset consumed by official ACP.

    write() stages bytes up to one explicit budget. drain() requires one complete
    LF-terminated line because that is the owner's public write contract. Other
    separators, concurrent read/drain and writes during drain are rejected rather
    than pretending to implement a general-purpose socket StreamWriter.
    """
    def __init__(self, channel, *, max_buffer_bytes):
        if type(max_buffer_bytes) is not int or not 1 <= max_buffer_bytes <= MAX_STDIN_BYTES:
            raise ValueError('invalid ACP byte buffer limit')
        callbacks = [getattr(channel, name, None) for name in ('read_line', 'write_line', 'stop_reads')]
        if any(not callable(fn) or inspect.iscoroutinefunction(fn) or inspect.isasyncgenfunction(fn)
               for fn in callbacks):
            raise ValueError('owned dialogue channel required')
        self._channel, self._limit = channel, max_buffer_bytes
        self._read_buffer, self._write_buffer = bytearray(), bytearray()
        self._read_task = self._write_task = self._close_task = None
        self._reading = self._closing = self.closed = False
        self._failure = None

    def _open(self):
        if self._closing:
            raise AcpStreamError('stream_closed')
        if self._failure is not None:
            raise self._failure

    async def _line(self):
        if self._read_task is not None:
            raise AcpStreamError('read_outcome_pending')
        task = self._read_task = asyncio.create_task(asyncio.to_thread(self._channel.read_line))
        try:
            line = await asyncio.shield(task)
        except asyncio.CancelledError:
            # Cancellation cannot stop the synchronous owner read. Retain exactly
            # this outcome until close wakes and drains it; never launch a retry.
            raise
        except DialogueReadStoppedV1 as exc:
            self._read_task = None
            if not self._closing:
                self._failure = self._failure or exc
            raise
        except EOFError:
            self._read_task = None
            raise asyncio.IncompleteReadError(bytes(self._read_buffer), None) from None
        except Exception as exc:
            self._read_task = None
            self._failure = self._failure or exc
            raise
        else:
            self._read_task = None
        if not isinstance(line, bytes) or not line.endswith(b'\n') or b'\n' in line[:-1]:
            self._failure = self._failure or AcpStreamError('invalid_owner_line')
            raise self._failure
        if len(line) > self._limit - len(self._read_buffer):
            self._failure = self._failure or AcpStreamError('read_limit')
            raise self._failure
        self._read_buffer.extend(line)

    async def _read(self, count=None):
        self._open()
        if self._reading or self._read_task is not None:
            raise AcpStreamError('concurrent_or_cancelled_read')
        self._reading = True
        try:
            while True:
                end = self._read_buffer.find(b'\n') + 1 if count is None else count
                if end and len(self._read_buffer) >= end:
                    result = bytes(self._read_buffer[:end])
                    del self._read_buffer[:end]
                    return result
                try:
                    await self._line()
                except asyncio.IncompleteReadError as exc:
                    self._read_buffer.clear()
                    raise asyncio.IncompleteReadError(exc.partial, count) from None
        finally:
            self._reading = False

    async def readuntil(self, separator=b'\n'):
        if separator != b'\n':
            raise AcpStreamError('unsupported_separator')
        return await self._read()

    async def readexactly(self, n):
        if type(n) is not int or not 0 <= n <= self._limit:
            raise AcpStreamError('invalid_read_size')
        if n == 0:
            self._open()
            return b''
        return await self._read(n)

    def write(self, data):
        self._open()
        if self._write_task is not None:
            raise AcpStreamError('write_outcome_pending')
        if not isinstance(data, bytes):
            raise TypeError('bytes required')
        if len(data) > self._limit - len(self._write_buffer):
            raise AcpStreamError('write_limit')
        self._write_buffer.extend(data)

    async def drain(self):
        self._open()
        if self._write_task is not None:
            raise AcpStreamError('concurrent_or_cancelled_drain')
        if not self._write_buffer:
            return
        if not self._write_buffer.endswith(b'\n') or b'\n' in self._write_buffer[:-1]:
            raise AcpStreamError('one_complete_line_required')
        payload = bytes(self._write_buffer)
        self._write_buffer.clear()
        async def write_owned():
            written = await asyncio.to_thread(self._channel.write_line, payload)
            if type(written) is not int or written != len(payload):
                raise AcpStreamError('short_write')
        task = self._write_task = asyncio.create_task(write_owned())
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            raise  # close retains/drains the outstanding write under owner bounds.
        except Exception as exc:
            self._write_task = None
            self._failure = self._failure or exc
            raise
        else:
            self._write_task = None

    async def _finish(self):
        try:
            self._channel.stop_reads()
        except Exception as exc:
            self._failure = self._failure or exc
        # No fd is closed here. The existing dialogue handler's finally remains
        # the stdin closer. Blocked writes still require owner deadline/settlement.
        pending = [(kind, task) for kind, task in (('read', self._read_task), ('write', self._write_task)) if task is not None]
        outcomes = await asyncio.gather(*(task for _, task in pending), return_exceptions=True)
        for (kind, _), outcome in zip(pending, outcomes):
            if isinstance(outcome, BaseException):
                if kind == 'read' and isinstance(outcome, (DialogueReadStoppedV1, EOFError)):
                    continue
                self._failure = self._failure or (outcome if isinstance(outcome, Exception) else AcpStreamError('worker_outcome_unavailable'))
        self._read_task = self._write_task = None
        self._read_buffer.clear()
        if self._write_buffer:
            self._failure = self._failure or AcpStreamError('undrained_write')
        self._write_buffer.clear()
        self.closed = True
        if self._failure is not None:
            raise self._failure

    async def close(self):
        if self._close_task is None:
            self._closing = True
            self._close_task = asyncio.create_task(self._finish())
        await drain_owned(self._close_task)
