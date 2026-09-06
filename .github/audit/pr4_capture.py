"""Record every collected test and deterministic shard; never change test outcomes."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

STATE = {"all_nodeids": [], "selected_nodeids": [], "completed": [], "failures": [],
         "skips": [], "xfails": [], "finished": False, "exitstatus": None}


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config, items):
    STATE["all_nodeids"] = [item.nodeid for item in items]
    total = int(os.environ.get("ORCH_SHARD_TOTAL", "1"))
    index = int(os.environ.get("ORCH_SHARD_INDEX", "0"))
    if not 0 <= index < total:
        raise pytest.UsageError("invalid audit shard")
    selected, excluded = [], []
    for position, item in enumerate(items):
        (selected if position % total == index else excluded).append(item)
    items[:] = selected
    config.hook.pytest_deselected(items=excluded)
    STATE["selected_nodeids"] = [item.nodeid for item in selected]
    STATE["shard_index"], STATE["shard_total"] = index, total
    _save()


def _save():
    Path(os.environ["ORCH_CAPTURE"]).write_text(
        json.dumps(STATE, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def pytest_runtest_logreport(report):
    if report.when == "teardown":
        STATE["completed"].append(report.nodeid)
    if report.failed:
        STATE["failures"].append({"nodeid": report.nodeid, "when": report.when,
                                  "detail": str(report.longrepr)})
    if report.skipped:
        STATE["skips"].append({"nodeid": report.nodeid, "reason": str(report.longrepr)})
    if hasattr(report, "wasxfail"):
        STATE["xfails"].append({"nodeid": report.nodeid, "reason": str(report.wasxfail)})
    if report.failed or (report.when == "teardown" and len(STATE["completed"]) % 25 == 0):
        _save()


def pytest_sessionfinish(session, exitstatus):
    STATE["finished"] = True
    STATE["exitstatus"] = int(exitstatus)
    _save()
