"""Read-only pytest collection/report evidence for the PR 4 audit jobs.

Shard by complete collected module names, including nested directories. A shard
is not a full-suite pass; the aggregate must account for every selected node.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path

import pytest

STATE: dict = {"schema": 1, "reports": [], "session_finished": False}


def save() -> None:
    path = Path(os.environ["AUDIT_EVIDENCE"]) / "pytest-capture.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(STATE, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config, items) -> None:
    total = int(os.environ.get("AUDIT_SHARDS", "6"))
    index = int(os.environ["AUDIT_SHARD"])
    if not 0 <= index < total:
        raise pytest.UsageError("invalid audit shard")
    collected = [item.nodeid for item in items]
    if len(collected) != len(set(collected)):
        raise pytest.UsageError("duplicate collected node identifiers")
    modules = sorted({node.split("::", 1)[0] for node in collected})
    owners = {module: ordinal % total for ordinal, module in enumerate(modules)}
    selected = [item for item in items if owners[item.nodeid.split("::", 1)[0]] == index]
    excluded = [item for item in items if owners[item.nodeid.split("::", 1)[0]] != index]
    if not selected:
        raise pytest.UsageError("empty audit shard")
    STATE.update({"shard": index, "shards": total, "collected": collected,
                  "selected": [item.nodeid for item in selected],
                  "deselected": [item.nodeid for item in excluded]})
    items[:] = selected
    config.hook.pytest_deselected(items=excluded)
    save()


def pytest_collectreport(report) -> None:
    if report.failed:
        STATE.setdefault("collection_errors", []).append(str(report.longrepr))
        save()


def pytest_runtest_logreport(report) -> None:
    row = {"nodeid": report.nodeid, "when": report.when, "outcome": report.outcome,
           "duration": report.duration}
    if report.failed or report.skipped:
        row["detail"] = str(report.longrepr)
    if hasattr(report, "wasxfail"):
        row["wasxfail"] = report.wasxfail
    STATE["reports"].append(row)
    save()


def pytest_sessionfinish(session, exitstatus) -> None:
    reports = STATE["reports"]
    completed = {row["nodeid"] for row in reports if row["when"] == "teardown"}
    STATE.update({"session_finished": True, "exit_status": int(exitstatus),
                  "missing_teardown": sorted(set(STATE.get("selected", [])) - completed),
                  "report_counts": dict(Counter(f"{row['when']}:{row['outcome']}" for row in reports))})
    save()
