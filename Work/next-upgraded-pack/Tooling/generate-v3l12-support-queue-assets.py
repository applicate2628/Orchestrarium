#!/usr/bin/env python3
"""Deterministic asset generator for V3L12-support-queue-visual-grounding (Phase 3 item F4).

Forked from the generate-n80-screenshot-grounding-assets.py pattern: draws one calibrated
dashboard screenshot with ten seeded visual defects at fixed pixel coordinates, plus six
false-positive traps that must NOT be flagged. This is a genuinely new scene (a support-ticket
triage console, not the release/incident dashboard N80 and N98 both draw) so the resulting PNG
is content-independent of N80's `actual-screenshot.png` and N98's `baseline.png`/`current.png`,
and independent of N21/N48's shared `panel-cases.json`-driven render (neither reads that file nor
imports `visual_panel.renderer`).

Run this script to (re)generate the PNG; it also prints the exact finding-center coordinates used,
so oracle/visual-review-oracle.json can be authored (or checked) from the same numbers -- single
source of truth, no hand-transcription drift between the drawing code and the scoring contract.
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
BUNDLE = ROOT / "Scenarios-v3" / "V3L12-support-queue-visual-grounding"
OUT = BUNDLE / "inputs" / "actual-screenshot.png"

WIDTH, HEIGHT = 1600, 1000


def font(size: int, bold: bool = False):
    names = [
        "arialbd.ttf" if bold else "arial.ttf",
        "segoeuib.ttf" if bold else "segoeui.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    ]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def rounded(draw: ImageDraw.ImageDraw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


# Finding centers: single source of truth shared between the drawing code below and the
# printed oracle snippet. Keys match the F01..F10 ids used in oracle/visual-review-oracle.json.
FINDING_CENTERS = {
    "F01": (94, 101),
    "F02": (1351, 101),
    "F03": (200, 236),
    "F04": (820, 229),
    "F05": (1088, 263),
    "F06": (622, 418),
    "F07": (78, 506),
    "F08": (540, 796),
    "F09": (1064, 610),
    "F10": (1300, 840),
}


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (WIDTH, HEIGHT), "#f5f7fb")
    draw = ImageDraw.Draw(img)

    f11 = font(11)
    f12 = font(12)
    f13 = font(13)
    f14 = font(14)
    f15 = font(15)
    f16 = font(16)
    f18 = font(18, True)
    f20 = font(20, True)
    f24 = font(24, True)
    f42 = font(42, True)

    # Decorative grid false-positive trap.
    for x in range(0, WIDTH, 50):
        draw.line((x, 0, x, HEIGHT), fill="#eaf0f6", width=1)
    for y in range(0, HEIGHT, 50):
        draw.line((0, y, WIDTH, y), fill="#eaf0f6", width=1)

    # Header with brand/logo false-positive trap (amber hex mark, distinct from N80's cyan one).
    draw.rectangle((0, 0, WIDTH, 64), fill="#151d2f")
    draw.polygon([(34, 14), (54, 6), (75, 14), (75, 38), (54, 48), (34, 38)], fill="#f4b942")
    draw.text((92, 16), "Support Queue", fill="#ffffff", font=f24)
    draw.text((270, 23), "ticket triage workspace", fill="#aab5c7", font=f15)

    # F01: search input defect -- icon overlaps placeholder text.
    rounded(draw, (48, 80, 460, 122), 8, "#ffffff", "#cbd5e1")
    draw.ellipse((66, 93, 84, 111), outline="#334155", width=2)
    draw.line((80, 108, 98, 122), fill="#334155", width=4)
    draw.rectangle((88, 86, 190, 118), fill="#ffffff")
    draw.text((92, 92), "Search tickets", fill="#536273", font=f16)
    draw.line((90, 88, 90, 117), fill="#151d2f", width=2)

    # Header actions: disabled Export CSV (trap) + primary Resolve batch button.
    rounded(draw, (1180, 80, 1290, 122), 8, "#eef2f7", "#cbd5e1")
    draw.text((1196, 94), "Export CSV", fill="#9aa6b8", font=f14)  # disabled false-positive trap.
    rounded(draw, (1314, 80, 1490, 122), 8, "#2458d8", "#1d46ad")
    draw.text((1338, 94), "Resolve batch", fill="#ffffff", font=f16)
    # F02: spinner overlaps the button label.
    draw.ellipse((1339, 90, 1363, 114), outline="#ffffff", width=4)
    draw.arc((1339, 90, 1363, 114), 55, 285, fill="#2458d8", width=5)

    # KPI cards row.
    rounded(draw, (48, 150, 430, 300), 8, "#ffffff", "#d7dee9")
    draw.text((72, 172), "Open tickets", fill="#536273", font=f16)
    draw.text((72, 206), "482", fill="#151d2f", font=f42)
    # F03: value clipped by an opaque divider drawn across it on purpose.
    draw.rectangle((200, 199, 430, 268), fill="#ffffff")
    draw.line((200, 199, 200, 268), fill="#b4becd", width=1)
    draw.text((72, 274), "vs last shift 61", fill="#8a96a8", font=f13)

    rounded(draw, (460, 150, 900, 300), 8, "#ffffff", "#d7dee9")
    draw.text((484, 172), "SLA breaches", fill="#536273", font=f16)
    draw.text((484, 206), "Payments queue", fill="#151d2f", font=f24)
    # F04: low-contrast status chip -- text color nearly matches the chip fill.
    rounded(draw, (760, 210, 880, 248), 19, "#35d07f", "#35d07f")
    draw.text((790, 222), "Stable", fill="#36ce81", font=f14)
    draw.text((484, 258), "Muted timestamp: 2 min ago", fill="#9aa6b8", font=f13)

    rounded(draw, (930, 150, 1552, 300), 8, "#ffffff", "#d7dee9")
    draw.text((954, 172), "First response trend", fill="#536273", font=f16)
    draw.text((954, 198), "SLA breach", fill="#151d2f", font=f18)
    # Decorative response-time sparkline trap.
    draw.line((980, 268, 1040, 236), fill="#2458d8", width=4)
    draw.line((1040, 236, 1100, 254), fill="#2458d8", width=4)
    draw.line((1100, 254, 1160, 216), fill="#2458d8", width=4)
    draw.line((1160, 216, 1260, 248), fill="#2458d8", width=4)
    # F05: alert marker detached from its own tooltip label.
    draw.ellipse((1080, 255, 1096, 271), fill="#dc2626")
    rounded(draw, (1180, 180, 1320, 210), 6, "#fff1f2", "#fb7185")
    draw.text((1196, 187), "SLA breach", fill="#9f1239", font=f13)

    # Ticket table.
    rounded(draw, (48, 340, 1000, 700), 8, "#ffffff", "#d7dee9")
    draw.text((72, 364), "Ticket queue", fill="#151d2f", font=f20)
    # Skeleton shimmer false-positive trap.
    rounded(draw, (760, 362, 930, 386), 12, "#edf2f7", "#edf2f7")
    draw.line((778, 364, 890, 384), fill="#f8fafc", width=5)

    draw.text((72, 418), "ID", fill="#536273", font=f14)
    draw.text((190, 418), "Subject", fill="#536273", font=f14)
    draw.text((600, 418), "Priority", fill="#536273", font=f14)
    # F06: sort caret overlaps the "Priority" column header text.
    draw.polygon([(614, 418), (630, 418), (622, 432)], fill="#151d2f")
    draw.text((820, 418), "Status", fill="#536273", font=f14)
    draw.line((48, 448, 1000, 448), fill="#e1e7f0", width=1)

    rows = [
        ("TQ-2091", "Refund not applied", "Priya", "waiting"),
        ("TQ-2092", "Webhook retries failing", "Omar", "open"),
        ("TQ-2093", "Card decline loop", "Lena", "open"),
        ("TQ-2094", "Address change request", "Sam", "queued"),
    ]
    y = 478
    for row_index, (item_id, subject, owner, state) in enumerate(rows):
        if row_index == 1:
            # F07: intentionally offset focus ring around the selected row.
            draw.rectangle((60, y - 14, 552, y + 54), outline="#2563eb", width=3)
        draw.rectangle((78, y - 1, 96, y + 17), outline="#94a3b8", width=2)
        if row_index == 1:
            draw.rectangle((82, y + 3, 92, y + 13), fill="#2563eb")
        draw.text((120, y - 4), item_id, fill="#151d2f", font=f14)
        draw.text((190, y - 4), subject, fill="#151d2f", font=f14)
        draw.text((600, y - 4), owner, fill="#151d2f", font=f14)
        chip_fill = "#ffe9d1" if state == "waiting" else "#e8f7ee"
        chip_text = "#8a4f00" if state == "waiting" else "#166534"
        rounded(draw, (818, y - 9, 922, y + 22), 15, chip_fill, chip_fill)
        draw.text((841, y - 3), state, fill=chip_text, font=f12)
        y += 58

    # Status tabs.
    rounded(draw, (48, 720, 1000, 940), 8, "#ffffff", "#d7dee9")
    draw.text((72, 748), "Queue status", fill="#151d2f", font=f20)
    tabs = [("New", 72), ("Open", 220), ("Pending", 380), ("Resolved", 560)]
    for label, x in tabs:
        draw.text((x, 796), label, fill="#151d2f", font=f18)
    # F08: progress underline crosses from "Pending" into "Resolved".
    draw.line((378, 796, 704, 796), fill="#2458d8", width=5)
    draw.text((72, 872), "3 tickets waiting on customer reply", fill="#536273", font=f15)

    # Right panel: channel legend.
    rounded(draw, (1030, 340, 1552, 700), 8, "#ffffff", "#d7dee9")
    draw.text((1054, 364), "Channel legend", fill="#151d2f", font=f20)
    colors = ["#e9f5ff", "#b8dcff", "#80c2ff", "#4394ed", "#2458d8"]
    for i, color in enumerate(colors):
        draw.rectangle((1062 + i * 62, 420, 1110 + i * 62, 592), fill=color)
    draw.text((1054, 616), "Legend", fill="#536273", font=f14)
    # F09: "Escalated" swatch drawn far from its own label.
    draw.rectangle((1054, 600, 1074, 620), fill="#d923d9")
    draw.text((1200, 596), "Escalated", fill="#151d2f", font=f14)

    # Bottom-right: workspace actions.
    rounded(draw, (1030, 720, 1552, 940), 8, "#ffffff", "#d7dee9")
    draw.text((1054, 748), "Workspace actions", fill="#151d2f", font=f20)
    rounded(draw, (1294, 824, 1490, 872), 8, "#151d2f", "#151d2f")
    draw.text((1330, 840), "Auto-assign", fill="#ffffff", font=f16)
    # F10: completion toast overlaps the Auto-assign button beneath it.
    rounded(draw, (1122, 796, 1492, 868), 8, "#fff4d6", "#f0b429")
    draw.text((1148, 806), "Auto-assign complete", fill="#5c4200", font=f16)
    draw.text((1148, 832), "12 tickets routed", fill="#5c4200", font=f13)

    img.save(OUT)
    print(OUT)
    print(json.dumps(FINDING_CENTERS, indent=2))


if __name__ == "__main__":
    main()
