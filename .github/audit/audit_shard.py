"""Audit-only pytest partitioning and machine-readable execution evidence."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess

import pytest


def _report_dir() -> Path:
    path = Path(os.environ["AUDIT_REPORT_DIR"])
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config, items):
    total = int(os.environ["AUDIT_SHARDS"])
    index = int(os.environ["AUDIT_INDEX"])
    if not 0 <= index < total:
        raise pytest.UsageError("invalid audit shard index")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if head != os.environ["AUDIT_EXPECTED_HEAD"]:
        raise pytest.UsageError("audit checkout moved before collection")
    ordered = sorted(items, key=lambda item: (hashlib.sha256(item.nodeid.encode()).digest(), item.nodeid))
    identifiers = [item.nodeid for item in ordered]
    if len(set(identifiers)) != len(identifiers):
        raise pytest.UsageError("audit collection has duplicate node identifiers")
    selected = ordered[index::total]
    if not selected:
        raise pytest.UsageError("empty audit partition")
    kept = {id(item) for item in selected}
    deselected = [item for item in items if id(item) not in kept]
    items[:] = selected
    config.hook.pytest_deselected(items=deselected)
    inventory = {
        "head": head,
        "os": os.name,
        "index": index,
        "shards": total,
        "collected": identifiers,
        "selected": [item.nodeid for item in selected],
        "collection_sha256": hashlib.sha256(json.dumps(identifiers).encode()).hexdigest(),
    }
    (_report_dir() / "inventory.json").write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")


def pytest_runtest_logreport(report):
    row = {
        "nodeid": report.nodeid,
        "when": report.when,
        "outcome": report.outcome,
        "duration": report.duration,
        "subtest": hasattr(report, "context"),
    }
    if report.failed:
        row["failure"] = report.longreprtext
    elif report.skipped:
        row["skip_reason"] = str(report.longrepr)
    with (_report_dir() / "reports.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=True) + "\n")
    if report.failed:
        print(f"\nAUDIT FAILURE: {report.nodeid} [{report.when}]\n{report.longreprtext}\n", flush=True)


def pytest_sessionfinish(session, exitstatus):
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if head != os.environ["AUDIT_EXPECTED_HEAD"]:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
    (_report_dir() / "exit.json").write_text(
        json.dumps({"exitstatus": int(session.exitstatus), "head": head}) + "\n", encoding="utf-8"
    )
