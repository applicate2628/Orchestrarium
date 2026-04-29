from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from model_view_owned import build_view_state


def test_hidden_rows_are_filtered():
    rows = [
        {"id": "row-b", "visible": False, "priority": 5},
        {"id": "row-a", "visible": True, "priority": 1},
    ]
    assert build_view_state(rows, "row-a")["visible_ids"] == ["row-a"]


def test_proxy_order_uses_priority():
    rows = [
        {"id": "row-a", "visible": True, "priority": 1},
        {"id": "row-c", "visible": True, "priority": 3},
        {"id": "row-b", "visible": True, "priority": 2},
    ]
    assert build_view_state(rows, "row-a")["visible_ids"] == ["row-c", "row-b", "row-a"]


def test_hidden_selection_falls_back_and_syncs_detail():
    rows = [
        {"id": "row-a", "visible": True, "priority": 1},
        {"id": "row-b", "visible": False, "priority": 5},
    ]
    state = build_view_state(rows, "row-b")
    assert state["selected_id"] == "row-a"
    assert state["detail_id"] == "row-a"


if __name__ == "__main__":
    test_hidden_rows_are_filtered()
    test_proxy_order_uses_priority()
    test_hidden_selection_falls_back_and_syncs_detail()
    print("S18 direct tests PASS")
