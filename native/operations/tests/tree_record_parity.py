"""Compare borrowed Rust records with the pinned receiving Python parser."""

import argparse
import hashlib
from pathlib import Path
import random
import subprocess
from types import SimpleNamespace

from tree_walk_parity import driver_input, loop_from, run_reference


class Refusal:
    def __init__(self, code, reason):
        self.code = code
        self.reason = reason


def receiving_parser(source):
    start = source.index("def _parse_tree(")
    end = source.index("\n\ndef _line_limit_refusal", start)
    region = dict(
        GitObjectFormat=SimpleNamespace,
        _SHA1_OBJECT_FORMAT=SimpleNamespace(raw_length=20),
        Refusal=Refusal,
        _refusal=Refusal,
        TreeEntry=lambda kind, name, oid, mode: SimpleNamespace(
            kind=kind, name=name, oid=bytes.fromhex(oid), mode=mode
        ),
    )
    exec(source[start:end], region)
    return region["_parse_tree"]


def examples(width, leaf, subtree):
    def row(mode, name, oid):
        return mode + b" " + name + b"\0" + oid

    valid = b"".join(row(m, p, o) for m, p, o in (
        (b"40000", b"shared", subtree), (b"040000", b"another", subtree),
        (b"100644", b"normal", leaf), (b"100755", b"\xff", leaf),
        (b"120000", b"line\nfilename", leaf), (b"160000", b"name with space", leaf),
    ))
    yield b""
    yield valid
    yield from (valid[:end] for end in range(len(valid)))
    yield row(b"100644", b"", leaf)
    yield row(b"100644", b"has/slash", leaf)
    yield row(b"000000", b"bogus-mode", leaf)
    yield row(b"000000", b"bad/path", leaf)
    yield row(b"100644", b"not-split", leaf) + b"\x00"
    yield row(b"100644", b"short-after-valid", leaf)[:-1] + b""
    yield row(b"100644", b"all-\xff", b"\xff" * width)
    rng = random.Random(width)
    for _ in range(256):
        raw = bytearray(valid)
        for _ in range(rng.randrange(1, 5)):
            raw[rng.randrange(len(raw))] = rng.randrange(256)
        yield bytes(raw)


def expected(parser, raw, width):
    entries = parser(raw, SimpleNamespace(raw_length=width))
    if isinstance(entries, Refusal):
        return f"R {entries.code} {entries.reason}"
    return "\n".join([
        *(f"E {r.kind} {r.mode} {r.name.hex()} {r.oid.hex()}" for r in entries),
        "R ok",
    ])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--driver", required=True, type=Path)
    ap.add_argument("--source", required=True, type=Path)
    args = ap.parse_args()
    raw_source = args.source.read_bytes()
    source = raw_source.decode("utf-8")
    parser = receiving_parser(source)
    digest = hashlib.sha256()
    count = 0
    for width in (20, 32):
        root, subtree, leaf = (bytes([n]) * width for n in range(1, 4))
        frames = list(examples(width, leaf, subtree))
        wire = "".join(f"{width} {raw.hex() or '-'}\n" for raw in frames)
        check = "\n".join(expected(parser, raw, width) for raw in frames) + "\n"
        observed = subprocess.run([args.driver, "--records"], input=wire, encoding="ascii",
                                  capture_output=True, check=True, timeout=30).stdout
        if observed != check:
            raise SystemExit(f"record/order/refusal mismatch ({width}-byte IDs)")
        digest.update(check.encode("ascii"))
        count += len(frames)

        # The first record fixture includes a reused subtree under two names.
        child = b"100644 last\0" + leaf
        graph = {oid: parser(raw, SimpleNamespace(raw_length=width))
                 for oid, raw in ((root, frames[1]), (subtree, child))}
        trees = set(graph)
        opts = (root, graph, trees, {leaf}, 128, 8, 0)
        trace = run_reference(loop_from(source), *opts)
        lines = driver_input(*opts).splitlines()[:2]
        lines += [f"P {oid.hex()} new {raw.hex()}".encode("ascii")
                  for oid, raw in ((root, frames[1]), (subtree, child))]
        walked = subprocess.run([args.driver], input=b"\n".join(lines)+b"\n",
                                capture_output=True, check=True, timeout=30).stdout
        if walked.replace(b"\r\n", b"\n") != trace:
            raise SystemExit(f"parsed-record walk mismatch ({width}-byte IDs)")
        digest.update(trace)
    print(f"parser_cases={count} composed_cases=2 sha256={digest.hexdigest()} "
          f"source_sha256={hashlib.sha256(raw_source).hexdigest()}")


if __name__ == "__main__":
    main()
