#!/usr/bin/env python3
"""Load the reviewed modular Stage 0 verifier without ambient import paths."""
from __future__ import annotations
import importlib.util
import sys
from pathlib import Path


def _load(name: str, filename: str):
    path = Path(__file__).resolve().with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load Stage 0 module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_runtime = _load("stage0_runtime", "stage0_runtime.py")
_evidence = _load("stage0_evidence", "stage0_evidence.py")
_orchestrator = _load("stage0_orchestrator", "stage0_orchestrator.py")
for _module in (_runtime, _evidence, _orchestrator):
    for _name, _value in vars(_module).items():
        if not _name.startswith("__"):
            globals()[_name] = _value

if __name__ == "__main__":
    raise SystemExit(main())
