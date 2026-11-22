"""Rust matcher frame validation at the scanner boundary."""
import json
from pathlib import Path
import re
import runpy

import pytest


WIRE = runpy.run_path(str(Path(__file__).resolve().parents[1]
                          / "scripts/universal-hooks/scripts/publication_match_wire.py"))
decode = WIRE["decode_batch"]
rules = ((True, re.compile(r"(ab)(x)?")), (False, re.compile(r"(b)")))


def frame(value):
    return json.dumps(value).encode("ascii") + b"\n"


def test_utf8_offsets_and_absent_capture_are_preserved():
    hits = [[[0, [[2, 4], [2, 4], None]], [1, [[3, 4], [3, 4]]]]]
    observed, = decode(frame(hits), (("éab", False),), rules)
    assert [(rule, match.span(), match.groups()) for rule, match in observed] == [
        (0, (1, 3), ("ab", None)), (1, (2, 3), ("b",)),
    ]


@pytest.mark.parametrize("value", [
    [],
    [[[0, [[1, 4], [2, 4], None]]]],  # Continuation byte, not a character boundary.
    [[[0, [[2, 4], [2, 3], None]]]],  # A capture is not what the rule matched.
    [[[True, [[3, 4], [3, 4]]]]],
    [[[2, [[3, 4], [3, 4]]]]],
    [[[0, [[2, 4], [2, 4], None]], [0, [[2, 4], [2, 4], None]]]],
    [[[1, [[3, 4], [3, 4]]], [0, [[2, 4], [2, 4], None]]]],
    [[[0, [[2, 4], [2, 4], [4, 4]]]]],
])
def test_malformed_frame_does_not_return_observations(value):
    with pytest.raises(ValueError, match="invalid matcher frame"):
        decode(frame(value), (("éab", False),), rules)


def test_binary_rows_do_not_admit_text_only_rules():
    with pytest.raises(ValueError, match="invalid matcher frame"):
        decode(frame([[[1, [[1, 2], [1, 2]]]]]), (("ab", True),), rules)


def test_length_is_not_success_if_the_frame_is_unterminated():
    with pytest.raises(ValueError, match="invalid matcher frame"):
        decode(b"[[]]", (("", False),), rules)

def test_frames_cross_pipe_chunks_without_losing_the_following_frame():
    import asyncio

    async def verify():
        reader = asyncio.StreamReader(limit=64 * 1024)
        reader.feed_data(b"[" + b" " * (150 * 1024) + b"]\n[]\n")
        reader.feed_eof()
        stream = WIRE["FrameReader"](reader)
        deadline = asyncio.get_running_loop().time() + 2
        assert await stream.read(deadline) == b"[" + b" " * (150 * 1024) + b"]\n"
        assert await stream.read(deadline) == b"[]\n"

    asyncio.run(verify())


def test_eof_before_delimiter_is_not_a_frame():
    import asyncio

    async def verify():
        reader = asyncio.StreamReader()
        reader.feed_data(b"[[]]")
        reader.feed_eof()
        stream = WIRE["FrameReader"](reader)
        with pytest.raises(ValueError, match="incomplete matcher frame"):
            await stream.read(asyncio.get_running_loop().time() + 2)

    asyncio.run(verify())
