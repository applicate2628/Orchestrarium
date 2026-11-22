"""Validate lexical matcher output before the Python policy consumes it."""

import json


PROTOCOL_HEADER = b"orche-match-spans-v1\n"


def decode_batch(frame, rows, rules):
    """Return ordered rule/match pairs, or reject the entire frame."""
    try:
        if not frame.endswith(b"\n") or b"\n" in frame[:-1]:
            raise ValueError
        result = json.loads(frame)
        if not isinstance(result, list) or len(result) != len(rows):
            raise ValueError

        return tuple(_decode_row(row, text, binary, rules)
                     for row, (text, binary) in zip(result, rows, strict=True))
    except (IndexError, RecursionError, TypeError, ValueError):
        # Neither content nor individual captures belong in diagnostics.
        raise ValueError("invalid matcher frame") from None


def _decode_row(row, text, binary, rules):
    if not isinstance(row, list):
        raise ValueError
    if not row:
        return ()

    data = text.encode("utf-8")
    offsets = {0}
    for entry in row:
        if not isinstance(entry, list) or len(entry) != 2:
            raise ValueError
        rule_id, spans = entry
        if type(rule_id) is not int or not 0 <= rule_id < len(rules):
            raise ValueError
        binary_rule, rule = rules[rule_id]
        if binary and not binary_rule:
            raise ValueError
        if not isinstance(spans, list) or len(spans) != 1 + rule.groups or spans[0] is None:
            raise ValueError
        for span in spans:
            if span is None:
                continue
            if not isinstance(span, list) or len(span) != 2:
                raise ValueError
            start, end = span
            if type(start) is not int or type(end) is not int or not 0 <= start <= end <= len(data):
                raise ValueError
            offsets.update(span)

    positions = {0: 0}
    previous = position = 0
    for offset in sorted(offsets):
        position += len(data[previous:offset].decode("utf-8"))
        positions[offset] = position
        previous = offset

    observations = []
    previous_key = (-1, -1)
    for rule_id, spans in row:
        coordinates = tuple((-1, -1) if span is None
                            else (positions[span[0]], positions[span[1]]) for span in spans)
        start, end = coordinates[0]
        key = (rule_id, start)
        if start == end or key <= previous_key:
            raise ValueError
        match = rules[rule_id][1].match(text, start)
        if match is None or match.regs != coordinates:
            raise ValueError
        previous_key = key
        observations.append((rule_id, match))
    return tuple(observations)

class FrameReader:
    """Read newline frames across the bounded owner pipe's transport chunks."""

    def __init__(self, stream):
        self._stream = stream
        self._next = b""

    async def read(self, deadline):
        import asyncio

        frame = bytearray()
        # No new admission quota: the existing scanner owns the deadline.
        async with asyncio.timeout_at(deadline):
            while True:
                chunk = self._next or await self._stream.read(64 * 1024)
                if not chunk:
                    raise ValueError("incomplete matcher frame")
                line, delimiter, self._next = chunk.partition(b"\n")
                frame.extend(line)
                if delimiter:
                    frame.extend(delimiter)
                    return bytes(frame)

    async def eof(self, deadline):
        import asyncio

        async with asyncio.timeout_at(deadline):
            return not self._next and not await self._stream.read(1)


def _pattern_source(pattern):
    import re

    flags = ((re.I, "i"), (re.M, "m"), (re.S, "s"), (re.X, "x"))
    if pattern.flags & ~(re.U | sum(flag for flag, _ in flags)):
        raise ValueError("unsupported matcher rule flags")
    selected = "".join(letter for flag, letter in flags if pattern.flags & flag)
    return (f"(?{selected})" if selected else "") + pattern.pattern


class MatcherExchange:
    """One sequential exchange over the scanner-owned child's pipes."""

    def __init__(self, reader, writer, rules):
        self._reader = FrameReader(reader)
        self._writer = writer
        self._rules = rules
        self._started = False

    async def _write(self, value, deadline):
        import asyncio

        async with asyncio.timeout_at(deadline):
            data = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self._writer.write(data + b"\n")
            await self._writer.drain()

    async def match(self, rows, deadline):
        if not self._started:
            await self._write([{"regex": _pattern_source(pattern), "binary": binary}
                               for binary, pattern in self._rules], deadline)
            if await self._reader.read(deadline) != PROTOCOL_HEADER:
                raise ValueError("unexpected matcher protocol")
            self._started = True
        await self._write([{"text": text, "binary": binary} for text, binary in rows], deadline)
        return decode_batch(await self._reader.read(deadline), rows, self._rules)

    async def eof(self, deadline):
        return await self._reader.eof(deadline)
