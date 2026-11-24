"""Compare batch decoding and traversal using synthetic and native Git frames."""
import argparse
import asyncio
import hashlib
import os
import subprocess
import tempfile
from itertools import chain
from pathlib import Path
from types import SimpleNamespace

from git_batch_parity import object_request, receiving_reader, reference
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
        ("corrupt_root_payload", root, {root: frame(root, bytes((root_raw[0] ^ 1,)) + root_raw[1:]), child: child_frame}),
        ("corrupt_child_payload", root, {root: root_frame, child: frame(child, bytes((child_raw[0] ^ 1,)) + child_raw[1:])}),
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


def native_git_fixtures(algorithm, scratch, reader_type):
    """Obtain unmodified stdout frames from Git in a disposable repository."""
    with tempfile.TemporaryDirectory(prefix="git-frames-", dir=scratch) as root:
        reader = reader_type()
        env = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
        env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_ALLOW_PROTOCOL="file")

        def git(*arguments, data=b""):
            return subprocess.run(
                ["git", *arguments], cwd=root, env=env, input=data, capture_output=True,
                check=True, timeout=15,
            ).stdout

        def write(kind, raw):
            oid = bytes.fromhex(git("hash-object", "-t", kind, "-w", "--stdin", data=raw).decode().strip())
            assert oid == object_id(raw, kind.encode("ascii"), algorithm)
            return oid

        def batch(oid):
            return git(*reader._argv, data=object_request(reader, oid.hex().encode("ascii")))

        git("init", "--quiet", "--bare", "--template=", f"--object-format={algorithm}")
        leaf = write("blob", b"git fixture\n")
        child = write("tree", entry(b"100644", b"nested.txt", leaf))
        tree = write("tree", entry(b"40000", b"dir", child) + entry(b"100755", b"root.txt", leaf))
        empty = write("tree", b"")
        absent = object_id(b"unwritten tree", b"tree", algorithm)
        missing_parent = write("tree", entry(b"40000", b"missing", absent))

        absent_frame = batch(absent)
        assert absent_frame == absent.hex().encode("ascii") + b" missing\n"
        yield "native_valid", tree, {tree: batch(tree), child: batch(child)}, leaf, {tree, child}
        yield "native_empty", empty, {empty: batch(empty)}, leaf, {empty}
        yield "native_missing_child", missing_parent, {missing_parent: batch(missing_parent),
                                                        absent: absent_frame}, leaf, {missing_parent, absent}


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--driver", type=Path, required=True)
    cli.add_argument("--source", type=Path, required=True)
    cli.add_argument("--git-scratch", type=Path, help="Existing parent for disposable native Git fixtures")
    args = cli.parse_args()
    raw_source = args.source.read_bytes()
    source = raw_source.decode("utf-8")
    reader, parse, loop = receiving_reader(source), receiving_parser(source), loop_from(source)
    checked = lines = 0
    digest = hashlib.sha256()
    for algorithm, width in (("sha1", 20), ("sha256", 32)):
        cases = fixtures(algorithm)
        if args.git_scratch is not None:
            cases = chain(cases, native_git_fixtures(algorithm, args.git_scratch, reader))
        for case, root, frames, leaf, trees in cases:
            graph = {}
            for oid, wire in frames.items():
                result, = asyncio.run(reference(reader, wire, oid.hex().encode("ascii"), "tree", 1))
                if result.startswith("R "):
                    graph[oid] = Refusal("owner", result[2:])
                else:
                    raw = bytes.fromhex(result[7:]) if result != "F tree -" else b""
                    if object_id(raw, b"tree", algorithm) != oid:
                        assert case in {"corrupt_root_payload", "corrupt_child_payload"}
                        graph[oid] = Refusal("owner", "PS-MSG-FRAME identity")
                        continue
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
            elif case == "native_valid":
                rows = expected.splitlines()
                assert sum(r.startswith(b"S ") for r in rows) == 2 and rows[-1] == b"R ok"
            elif case == "native_empty":
                rows = expected.splitlines()
                assert not any(r.startswith(b"S ") for r in rows) and rows[-1] == b"R ok"
            elif case == "native_missing_child":
                rows = expected.splitlines()
                assert not any(r.startswith(b"S ") for r in rows)
                assert rows[-1].startswith(b"R ") and rows[-1] != b"R ok"
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
