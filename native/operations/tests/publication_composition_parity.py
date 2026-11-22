"""Compose verified synthetic batch input with tree decoding and traversal."""
import argparse
import asyncio
import hashlib
from pathlib import Path
import subprocess
from types import SimpleNamespace

from git_batch_parity import receiving_reader, reference
from tree_record_parity import Refusal as RecordRefusal, receiving_parser
from tree_walk_parity import Refusal, loop_from, run_reference


def object_id(raw, kind, algorithm):
    return hashlib.new(
        algorithm, kind + b" " + str(len(raw)).encode("ascii") + b"\0" + raw
    ).digest()


def frame(oid, raw, kind=b"tree"):
    return oid.hex().encode("ascii") + b" " + kind + b" " + str(len(raw)).encode() + b"\n" + raw + b"\n"


def entry(mode, name, oid):
    return mode + b" " + name + b"\0" + oid


def fixtures(algorithm):
    leaf = object_id(b"fixture\n", b"blob", algorithm)
    child_raw = entry(b"100755", b"odd-\xff\nname", leaf)
    child = object_id(child_raw, b"tree", algorithm)
    root_raw = (entry(b"40000", b"first", child) + entry(b"040000", b"second", child)
                + entry(b"100644", b"root.txt", leaf))
    root = object_id(root_raw, b"tree", algorithm)
    root_frame, child_frame = frame(root, root_raw), frame(child, child_raw)
    child_hex = child.hex().encode()
    root_hex = root.hex().encode()
    bad = b"100755 incomplete"
    bad_oid = object_id(bad, b"tree", algorithm)
    bad_root = entry(b"40000", b"invalid", bad_oid)
    bad_root_oid = object_id(bad_root, b"tree", algorithm)
    empty = object_id(b"", b"tree", algorithm)
    cases = (
        ("valid", root, {root: root_frame, child: child_frame}),
        ("unused_malformed_frame", root, {root: root_frame, child: child_frame, empty: b"unused"}),
        ("empty", empty, {empty: frame(empty, b"")}),
        ("wrong_root_identity", root, {root: child_frame, child: child_frame}),
        ("wrong_child_identity", root, {root: root_frame, child: root_frame}),
        ("wrong_root_type", root, {root: frame(root, root_raw, b"blob"), child: child_frame}),
        ("wrong_child_type", root, {root: root_frame, child: frame(child, child_raw, b"tag")}),
        ("missing_root", root, {root: root_hex + b" missing\n"}),
        ("missing_child", root, {root: root_frame, child: child_hex + b" missing\n"}),
        ("unknown_child_request", root, {root: root_frame}),
        ("truncated_child_header", root, {root: root_frame, child: child_hex}),
        ("truncated_child_body", root, {root: root_frame, child: child_frame[:-2]}),
        ("missing_child_delimiter", root, {root: root_frame, child: child_frame[:-1]}),
        ("wrong_child_delimiter", root, {root: root_frame, child: child_frame[:-1] + b"!"}),
        ("malformed_authenticated_tree", bad_root_oid,
         {bad_root_oid: frame(bad_root_oid, bad_root), bad_oid: frame(bad_oid, bad)}),
    )
    for case, root, frames in cases:
        yield case, root, frames, leaf, ({root, child} & frames.keys()) | {root}


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--driver", type=Path, required=True)
    cli.add_argument("--source", type=Path, required=True)
    args = cli.parse_args()
    raw_source = args.source.read_bytes()
    source = raw_source.decode("utf-8")
    reader, parse, loop = receiving_reader(source), receiving_parser(source), loop_from(source)
    checked = lines = 0
    digest = hashlib.sha256()
    for algorithm, width in (("sha1", 20), ("sha256", 32)):
        for case, root, frames, leaf, trees in fixtures(algorithm):
            graph = {}
            for oid, wire in frames.items():
                result, = asyncio.run(reference(reader, wire, oid.hex().encode("ascii"), "tree", 1))
                if result.startswith("R "):
                    graph[oid] = Refusal("owner", result[2:])
                else:
                    raw = bytes.fromhex(result[7:]) if result != "F tree -" else b""
                    assert object_id(raw, b"tree", algorithm) == oid
                    row = parse(raw, SimpleNamespace(raw_length=width))
                    graph[oid] = (Refusal("owner", f"{row.code} {row.reason}")
                                  if isinstance(row, RecordRefusal) else row)
            expected = run_reference(loop, root, graph, trees, {leaf}, 4096, 12, 0)
            if case == "valid":
                rows = expected.splitlines()
                assert {bytes.fromhex(r[2:].decode()) for r in rows if r.startswith(b"T ")} == trees
                subjects = [r.split() for r in rows if r.startswith(b"S ")]
                assert len(subjects) == 3 and {bytes.fromhex(r[2].decode()) for r in subjects} == {leaf}
                assert sum(r.startswith(b"M ") for r in rows) == 5 and rows[-1] == b"R ok"
            for chunk in (1, 23, 65536):
                rows = [f"{root.hex()} 4096 12 0", f"B {leaf.hex()}"]
                rows.extend(f"F {oid.hex()} {'new' if oid in trees else 'known'} {chunk} {wire.hex() or '-'}"
                            for oid, wire in frames.items())
                actual = subprocess.run([args.driver], input="\n".join(rows)+"\n", encoding="ascii",
                                        capture_output=True, check=True, timeout=15).stdout.encode("ascii")
                if actual != expected:
                    raise SystemExit(f"composed refusal or event mismatch: {case}/{algorithm}/{chunk}")
                digest.update(expected)
                lines += expected.count(b"\n")
                checked += 1
    print(f"cases={checked} ordered_rows={lines} trace_sha256={digest.hexdigest()} "
          f"source_sha256={hashlib.sha256(raw_source).hexdigest()}")


if __name__ == "__main__":
    main()
