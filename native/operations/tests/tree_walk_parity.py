"""Differential fixture test driven by the exact receiving Python walker."""

import argparse
import asyncio
import hashlib
from pathlib import Path
import subprocess
from types import SimpleNamespace


class Refusal:
    def __init__(self, code, reason):
        self.reason = reason


def loop_from(source):
    receiving_v3 = "    for commit_oid, root_tree in chain(commit_roots, direct_trees):"
    legacy = "    for commit_oid, root_tree in tree_roots:"
    marker = receiving_v3 if receiving_v3 in source else legacy
    start = source.index(marker)
    end = source.index("\n    for subject in direct_blobs:", start)
    loop = source[start:end]
    # This evaluates the canonical tree walk rather than a reimplementation.
    # The stubbed owner methods record admission requests without classifying.
    fn = """async def reference(root, graph, reached_unpublished_trees, index,
                        unpublished_trees, unpublished_blobs, _tree_traversal_guard,
                        load_tree, _MAX_PATH_BYTES, native, _refusal, Refusal):
    tree_roots = [(b"root-owner", root)]
    scan_deadline = 1
"""
    ns = {}
    if marker == receiving_v3:
        from itertools import chain

        ns["chain"] = chain
        fn += """    commit_roots, direct_trees = tree_roots, ()
    compact_frontier = False
    stack = []
    traversal_progress = progress()
    selected_blob = unpublished_blobs.__contains__
    def selected_tree_reached(oid):
        if oid not in unpublished_trees:
            return False
        reached_unpublished_trees.add(oid)
        return True
"""
        ns["progress"] = lambda: SimpleNamespace(step=lambda: None, finish=lambda: None)
    exec(fn + loop + "\n", ns)
    return ns["reference"]


def run_reference(loop, root, graph, trees, blobs, max_bytes, frontier_limit, expire):
    trace = []

    class Index:
        def add_metadata(self, oid, path):
            trace.append(f"M {oid.hex()} {path.hex()}")
            return False

        def add(self, subject, mode):
            _, path, blob = subject
            trace.append(f"S {path.hex()} {blob.hex()} {mode.encode('ascii').hex()}")
            return True

    class Reached:
        def add(self, oid):
            trace.append(f"T {oid.hex()}")

    checked = 0

    def guard(*, deadline, frontier):
        nonlocal checked
        checked += 1
        trace.append(f"G {frontier}")
        if expire and checked >= expire:
            return Refusal("owner", "deadline")
        return Refusal("owner", "tree-frontier") if frontier > frontier_limit else None

    async def load(oid):
        return graph.get(oid, Refusal("owner", "missing-tree"))

    result = asyncio.run(loop(root, graph, Reached(), Index(), trees, blobs, guard, load,
                              max_bytes, True, Refusal, Refusal))
    trace.append("R " + ("ok" if result is None else result.reason))
    return ("\n".join(trace) + "\n").encode("ascii")


def driver_input(root, graph, trees, blobs, max_bytes, frontier, expire):
    rows = [f"{root.hex()} {max_bytes} {frontier} {expire}"]
    rows.extend(f"B {oid.hex()}" for oid in sorted(blobs))
    for oid, entries in graph.items():
        rows.append(f"T {oid.hex()} {'new' if oid in trees else 'known'}")
        rows.extend(f"E {oid.hex()} {e.kind} {e.name.hex()} {e.oid.hex()} {e.mode}" for e in entries)
    return ("\n".join(rows) + "\n").encode("ascii")


def fixtures(width):
    root, a, b, c, file, gitlink = (bytes([n]) * width for n in range(1, 7))
    def entry(kind, name, oid, mode=None):
        return SimpleNamespace(kind=kind, name=name, oid=oid,
                               mode=mode or {"blob":"100644","tree":"40000","gitlink":"160000"}[kind])
    shared = {
        root: [entry("tree", b"A", a, "040000"),entry("tree", b"B", a),entry("gitlink", b"module", gitlink),
               entry("blob", b"\xff", file, "100755"),entry("tree", b"old", c)],
        a: [entry("blob", b"target", file, "120000"), entry("tree", b"sub", b)],
        b: [entry("blob", b"nested", file)],
        c: [entry("blob", b"unchanged", file)],
    }
    yield "shared_subtree", (root, shared, {root,a,b}, {file}, 64, 8, 0)
    yield "known_tree_has_new_blob_subject", (root, shared, set(), {file}, 64, 8, 0)
    yield "known_blob_has_new_tree_metadata", (root, shared, {root,a,b}, set(), 64, 8, 0)
    yield "frontier_exact_limit", (root, shared, {root,a,b}, {file}, 64, 3, 0)
    yield "frontier_exceeded", (root, shared, {root,a,b}, {file}, 64, 2, 0)
    yield "deadline_precedes_frontier", (root, shared, {root,a,b}, {file}, 64, 0, 2)
    yield "deadline_during_traversal", (root, shared, {root,a,b}, {file}, 64, 8, 14)
    yield "path_limit_exact", (root, shared, {root,a,b}, {file}, 12, 8, 0)
    yield "path_limit_exceeded", (root, shared, {root,a,b}, {file}, 11, 8, 0)
    yield "shared_empty_tree", (root, {root:[], a:[]}, {root,a}, set(), 1, 1, 0)
    yield "indirect_cycle", (root, {root:[entry("tree",b"a",a)],a:[entry("tree",b"b",root)]},
                             {root,a}, set(), 64, 8, 0)
    yield "missing_verified_record", (root, {root:[entry("tree",b"a",a)]},
                                       {root,a}, set(), 64, 8, 0)
    chain = [i.to_bytes(width,"big") for i in range(128, 258)]
    deep = {oid:[entry("tree",b"a",child)] for oid,child in zip(chain,chain[1:])}
    deep[chain[-1]] = [entry("blob",b"x",file)]
    yield "deep_tree_exact_path_limit", (chain[0],deep,set(chain),{file},259,1,0)
    yield "deep_tree_beyond_path_limit", (chain[0],deep,set(chain),{file},258,1,0)
    yield "wide_tree", (root,{root:[entry("blob", f"subject-{i:05d}".encode(),file)
                                     for i in range(65_536)]},{root},{file},64,1,0)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--driver", type=Path, required=True)
    p.add_argument("--source", type=Path, required=True)
    args = p.parse_args()
    raw = args.source.read_bytes()
    loop = loop_from(raw.decode("utf-8"))
    count = 0
    digest = hashlib.sha256()
    rows = 0
    for width in (20, 32):
        for case, data in fixtures(width):
            expected = run_reference(loop, *data)
            result = subprocess.run([str(args.driver)], input=driver_input(*data),
                                     capture_output=True, timeout=30, check=True)
            received = result.stdout.replace(b"\r\n", b"\n")
            if received != expected:
                raise SystemExit(f"ordered event or refusal mismatch: {case}, width {width}")
            digest.update(expected)
            rows += expected.count(b"\n")
            count += 1
    print(f"cases={count} trace_rows={rows} trace_sha256={digest.hexdigest()} source_sha256={hashlib.sha256(raw).hexdigest()}")


if __name__ == "__main__":
    main()
