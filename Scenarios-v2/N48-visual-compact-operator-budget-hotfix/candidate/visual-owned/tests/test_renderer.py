from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "candidate" / "visual-owned" / "src"
sys.path.insert(0, str(SRC))

from visual_panel.renderer import export_ppm, render_panel  # noqa: E402


def load_case() -> dict:
    payload = json.loads((ROOT / "inputs" / "panel-cases.json").read_text(encoding="utf-8"))
    return payload["cases"][0]


def test_missing_cell_stays_background():
    frame = render_panel(load_case())
    assert frame[6][6] == (17, 19, 24)


def test_selected_cell_has_focus_ring_and_additive_center():
    frame = render_panel(load_case())
    assert frame[5][13] == (250, 204, 21)
    assert frame[6][14] == (250, 62, 38)


def test_ppm_header_uses_width_then_height():
    frame = render_panel(load_case())
    assert export_ppm(frame).splitlines()[:3] == ["P3", "22 15", "255"]
