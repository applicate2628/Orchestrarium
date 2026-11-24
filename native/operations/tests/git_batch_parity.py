"""Check the Rust decoder against the receiving Python read method and framing."""
import argparse
import asyncio
import hashlib
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

from tree_record_parity import Refusal


def receiving_reader(source):
    from typing import Callable
    i = source.index("def _parse_batch_frame_header(")
    j = source.index("\ndef _parse_batch_check_frame(", i)
    reader_start = source.index("class _AsyncGitObjectReader:")
    constructor = source.index("    def __init__(", reader_start)
    constructor_end = source.index("\n    @property", constructor)
    k = source.index("    async def read(", reader_start)
    l = source.index("    async def classify(", k)
    ns = dict(Refusal=Refusal, _refusal=Refusal, ObjectReadSuccess=lambda *fields: fields,
              asyncio=asyncio, ReaderState=SimpleNamespace(CREATED=False, ACTIVE=True),
              _range_git_argv=lambda *args: args, OBJECT_REAP_ATTEMPT_SECONDS=3.0,
              _MAX_BLOB_BYTES=64*1048576, _MAX_COMMIT_TREE_BYTES=1048576,
              _READ_CHUNK_BYTES=65536, Callable=Callable)
    exec("from __future__ import annotations\n" + source[i:j] + "\nclass Reader:\n"
         + source[constructor:constructor_end] + "\n" + source[k:l], ns)
    return ns["Reader"]


def object_request(reader, oid):
    if reader._argv == ("cat-file", "--batch-command"):
        return b"contents " + oid + b"\n"
    if reader._argv == ("cat-file", "--batch"):
        return oid + b"\n"
    raise AssertionError("unqualified receiving reader command")


async def reference(reader_type, wire, oid, expected, attempts):
    reader = reader_type()
    reader._state = True
    requests = []
    request = object_request(reader, oid)
    stdout = asyncio.StreamReader(limit=65536)
    stdout.feed_data(wire)
    stdout.feed_eof()

    async def identity(awaitable, _deadline):
        return await awaitable

    async def drain():
        return None

    reader._process = SimpleNamespace(
        stdin=SimpleNamespace(write=requests.append, drain=drain), stdout=stdout
    )
    reader._within = identity
    reader._request_deadline = lambda _: None
    output = []
    for _ in range(attempts):
        result = await reader.read(oid.decode("ascii"), expected)
        assert requests.pop(0) == request and not requests
        if isinstance(result, Refusal):
            output.append(f"R {result.code} {result.reason}")
            break
        _, _, kind, payload = result
        output.append(f"F {kind} {payload.hex() or '-'}")
    return output


def fixtures(oid):
    blob = oid + b" blob "
    frame = blob + b"4\nA\x00\n\xff\n"
    yield frame, None, 1
    yield frame + frame, "blob", 2
    yield frame + blob + b"0\n\n", "blob", 2
    yield frame + b"partial", "blob", 2
    for end in range(len(frame)):
        yield frame[:end], None, 1
    for kind in (b"commit", b"tree", b"tag", b"blob", b"\xff", b""):
        for expected in (None, "tree"):
            yield oid+b" "+kind+b" 0\n\n", expected, 1
    for n in (b"+4", b"0_4", b"4\t", b"\v4\r", b"4_0", b"04", b"0004", b"-0",
              b"-0_0", b"-4", b"", b"4_", b"_4", b"0__4", b"++4", b"\xff", b"+\t4",
              b"9"*4320, b"9"*4300, b"9"*4301, b"67108864", b"67108865"):
        yield blob+n+b"\nABCD\n", None, 1
    for n in (b"1048576", b"1048577", b"0"):
        yield oid+b" tree "+n+b"\n\n", "tree", 1
    yield blob+b"4\nABCD!", None, 1
    yield oid+b" missing\n", None, 1
    yield b"f"*len(oid)+b" missing\n", None, 1
    yield b"f"*len(oid)+b" blob 0\n\n", None, 1
    yield oid+b" blob 0 extra\n\n", None, 1
    yield b"q"*65535 + b"\n", None, 1
    yield b"q"*65536 + b"\n", None, 1
    yield b"q"*65537 + b"\n", None, 1
    yield b"q"*65537, None, 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--driver", type=Path, required=True)
    ap.add_argument("--source", type=Path, required=True)
    args = ap.parse_args()
    py = args.source.read_bytes()
    reader_type = receiving_reader(py.decode("utf-8"))
    rows, expected = [], []
    for oid in (b"a"*40, b"a"*64):
        for wire, kind, attempts in fixtures(oid):
            oracle = asyncio.run(reference(reader_type, wire, oid, kind, attempts))
            for chunk in (1, 31, 512, 65537):
                rows.append(f"{oid.decode()} {kind or '-'} {chunk} {attempts} "
                            f"{sys.get_int_max_str_digits()} {wire.hex() or '-'}")
                expected.extend(oracle)
    data = subprocess.run([args.driver, "--frames"], input="\n".join(rows)+"\n",
                          encoding="ascii", capture_output=True, check=True, timeout=40)
    oracle = "\n".join(expected)+"\n"
    if data.stdout != oracle:
        raise SystemExit("structural batch frame parity failed")
    print(f"cases={len(rows)} byte_parity=yes "
          f"trace_sha256={hashlib.sha256(oracle.encode('ascii')).hexdigest()} "
          f"source_sha256={hashlib.sha256(py).hexdigest()}")


if __name__ == "__main__":
    main()
