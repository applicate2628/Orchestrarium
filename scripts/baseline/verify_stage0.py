#!/usr/bin/env python3
"""Assemble and execute the reviewed Stage 0 verifier fragments."""
from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

_FRAGMENT_RECORDS = (
    ("verify_stage0.part-00.pyfrag", "37abb235cb268185d5e3f18546cd075ca29f15e4b02e3f0fc4c53144038b6d9c", "49258b10e4bf843213557d7420f5154b29ee91d4"),
    ("verify_stage0.part-01.pyfrag", "94968cdf02e3e42b7ce517fb5f9214e24800f1bd7474489d325e3777e4502801", "24a8cb22480d03c03a7b177ea3fcba553dcd380b"),
    ("verify_stage0.part-02.pyfrag", "47d3c7bb72f7c94a7371791ec96aa8cbd75c66e35f3bdc5111bb06fc7950313a", "5edff4c8596929df9d70dc804cfb025dda6e22ec"),
    ("verify_stage0.part-03.pyfrag", "f64cb0117839c837890b03c624c4253eace6cf40d64256d2c551b5dccce7eb22", "f6839cc46a4109d128e141f143e6ae54beed1727"),
    ("verify_stage0.part-04.pyfrag", "cdce90bbe5ba049885268b1cfc69531a33237965c7df5cc5e5f4b00b2994c74b", "36545db5ccce1a07cf14947e5c6b6ab098144d24"),
    ("verify_stage0.part-05.pyfrag", "022caee2756f334a3b98d711b5deca242bc120cba9bf6bf1bb86451dd8375a76", "bb60ef66bb8a875ed25836f7cd59c2d0209a0389"),
    ("verify_stage0.part-06.pyfrag", "7bb25980e66e39ff4742a95d56a705f67b8ef008a462ef94f0635a64571e68a1", "89b295146e22619cad1b449baa07d1cfb890660d"),
)


def _read_fragment(root: Path, name: str, expected_sha256: str) -> bytes:
    path = root / name
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise RuntimeError(f"Stage 0 verifier fragment is not a private regular file: {path}")
        blocks = []
        digest = hashlib.sha256()
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            digest.update(block)
            blocks.append(block)
    finally:
        os.close(descriptor)
    if digest.hexdigest() != expected_sha256:
        raise RuntimeError(f"Stage 0 verifier fragment digest mismatch: {path}")
    return b"".join(blocks)


_root = Path(__file__).resolve().parent
_source = b"".join(
    _read_fragment(_root, name, sha256)
    for name, sha256, _git_blob in _FRAGMENT_RECORDS
)
exec(compile(_source, f"{__file__}::<reviewed-fragments>", "exec"), globals())
