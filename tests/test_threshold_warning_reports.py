from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import threading

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "_threshold_report_common", ROOT / "scripts/universal-hooks/scripts/hook_common.py"
)
common = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = common
SPEC.loader.exec_module(common)


def test_nonblocking_one_sanitized_report(tmp_path, monkeypatch):
    started = threading.Event()
    release = threading.Event()
    real_write = common._write_threshold_warning_report

    def blocked(home, rows):
        started.set()
        assert release.wait(5)
        return real_write(home, rows)

    monkeypatch.setattr(common, "_write_threshold_warning_report", blocked)
    warning = common.ThresholdWarning("scan", "seconds", 10, 12, 1)
    result = common.start_threshold_warning_report(
        [warning, common.ThresholdWarning("scan", "seconds", 10, 14, 2)],
        user_home=tmp_path,
    )
    try:
        assert started.wait(5)
        assert not result.done()
        assert not (tmp_path / ".orche").exists()
    finally:
        release.set()
    path = result.result(timeout=5)
    assert path.parent == tmp_path / ".orche" / "reports"
    assert list(path.parent.iterdir()) == [path]
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "version": 1,
        "kind": "threshold-warnings",
        "warnings": [{"stage": "scan", "unit": "seconds", "threshold": 10,
                      "observed": 12, "completed": 1}],
    }


def test_unwritable_report_directory_is_not_success(tmp_path):
    (tmp_path / ".orche").write_text("existing file", encoding="utf-8")
    warning = common.ThresholdWarning("scan", "seconds", 10, 12, 1)
    assert common.start_threshold_warning_report([warning], user_home=tmp_path).result(timeout=5) is None
    assert (tmp_path / ".orche").read_text(encoding="utf-8") == "existing file"


def test_free_form_input_not_persisted(tmp_path):
    with pytest.raises(ValueError):
        common.ThresholdWarning("raw repository content", "seconds", 10, 12, 1)
    with pytest.raises(ValueError):
        common.ThresholdWarning("scan", "seconds", 10, False, 1)
    assert common.start_threshold_warning_report([], user_home=tmp_path).result(timeout=5) is None
    assert list(tmp_path.iterdir()) == []


def test_linked_reports_directory_is_not_followed(tmp_path, monkeypatch):
    outside = tmp_path / "outside"
    outside.mkdir()
    app = tmp_path / ".orche"
    app.mkdir()
    try:
        (app / "reports").symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"test host cannot create directory symlinks: {exc}")
    warning = common.ThresholdWarning("scan", "seconds", 10, 12, 1)
    assert common.start_threshold_warning_report([warning], user_home=tmp_path).result(timeout=5) is None
    assert list(outside.iterdir()) == []
