#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "Scenarios-v2" / "N80-screenshot-grounding-review-v2" / "inputs" / "actual-screenshot.png"


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


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (1600, 1100), "#f5f7fb")
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
    for x in range(0, 1600, 50):
        draw.line((x, 0, x, 1100), fill="#eaf0f6", width=1)
    for y in range(0, 1100, 50):
        draw.line((0, y, 1600, y), fill="#eaf0f6", width=1)

    # Header with brand/logo false-positive trap.
    draw.rectangle((0, 0, 1600, 66), fill="#151d2f")
    draw.polygon([(34, 19), (54, 10), (75, 19), (75, 42), (54, 52), (34, 42)], fill="#4cc9f0")
    draw.text((92, 18), "Release Lens", fill="#ffffff", font=f24)
    draw.text((276, 25), "visual review workspace", fill="#aab5c7", font=f15)

    # Search input defect: icon and caret intrude into placeholder text.
    rounded(draw, (48, 82, 510, 128), 8, "#ffffff", "#cbd5e1")
    draw.ellipse((70, 95, 88, 113), outline="#334155", width=2)
    draw.line((84, 110, 103, 125), fill="#334155", width=4)
    draw.rectangle((96, 88, 194, 122), fill="#ffffff")
    draw.text((106, 96), "Search releases", fill="#536273", font=f16)
    draw.line((98, 92, 98, 121), fill="#151d2f", width=2)

    # Header actions.
    rounded(draw, (1180, 82, 1290, 128), 8, "#eef2f7", "#cbd5e1")
    draw.text((1212, 97), "Export", fill="#9aa6b8", font=f16)  # disabled false-positive trap.
    rounded(draw, (1314, 82, 1490, 128), 8, "#2458d8", "#1d46ad")
    draw.text((1362, 97), "Run audit", fill="#ffffff", font=f16)
    draw.ellipse((1339, 94, 1363, 118), outline="#ffffff", width=4)
    draw.arc((1339, 94, 1363, 118), 55, 285, fill="#2458d8", width=5)

    # KPI cards.
    rounded(draw, (48, 160, 520, 330), 8, "#ffffff", "#d7dee9")
    draw.text((80, 184), "Risk score", fill="#536273", font=f16)
    draw.text((80, 218), "128.4%", fill="#151d2f", font=f42)
    draw.rectangle((214, 211, 520, 286), fill="#ffffff")  # clips the value on purpose.
    draw.line((214, 211, 214, 286), fill="#b4becd", width=1)
    draw.text((80, 292), "Baseline delta +18.2", fill="#8a96a8", font=f13)

    rounded(draw, (550, 160, 1020, 330), 8, "#ffffff", "#d7dee9")
    draw.text((582, 184), "Service status", fill="#536273", font=f16)
    draw.text((582, 221), "Payments core", fill="#151d2f", font=f24)
    rounded(draw, (872, 226, 1000, 268), 20, "#35d07f", "#35d07f")
    draw.text((906, 238), "Healthy", fill="#36ce81", font=f14)  # low contrast on purpose.
    draw.text((582, 292), "Muted timestamp: 08:42 UTC", fill="#9aa6b8", font=f13)

    rounded(draw, (1050, 160, 1548, 330), 8, "#ffffff", "#d7dee9")
    draw.text((1082, 184), "Deploy trend", fill="#536273", font=f16)
    draw.text((1082, 214), "p95 breach", fill="#151d2f", font=f18)
    # Decorative trend sparkline plus intentionally detached alert marker.
    draw.line((1110, 280, 1165, 246), fill="#2458d8", width=4)
    draw.line((1165, 246, 1226, 266), fill="#2458d8", width=4)
    draw.line((1226, 266, 1290, 226), fill="#2458d8", width=4)
    draw.line((1290, 226, 1396, 260), fill="#2458d8", width=4)
    draw.ellipse((1200, 286, 1220, 306), fill="#dc2626")
    rounded(draw, (1322, 202, 1468, 234), 6, "#fff1f2", "#fb7185")
    draw.text((1338, 210), "p95 breach", fill="#9f1239", font=f13)

    # Main table.
    rounded(draw, (48, 370, 1020, 740), 8, "#ffffff", "#d7dee9")
    draw.text((80, 398), "Incident queue", fill="#151d2f", font=f20)
    # Skeleton shimmer false-positive trap.
    rounded(draw, (785, 395, 960, 420), 12, "#edf2f7", "#edf2f7")
    draw.line((805, 398, 915, 417), fill="#f8fafc", width=5)

    draw.text((80, 454), "ID", fill="#536273", font=f14)
    draw.text((200, 454), "Service", fill="#536273", font=f14)
    draw.text((610, 454), "Owner", fill="#536273", font=f14)
    draw.text((820, 454), "Status", fill="#536273", font=f14)
    draw.polygon([(836, 454), (852, 454), (844, 468)], fill="#151d2f")  # overlaps Status header.
    draw.line((48, 486, 1020, 486), fill="#e1e7f0", width=1)

    rows = [
        ("RL-4021", "Payment settlement", "Mira", "blocked"),
        ("RL-4022", "Webhook retries", "Ivan", "ready"),
        ("RL-4023", "Balance export", "Nora", "ready"),
        ("RL-4024", "Risk report", "Li", "queued"),
    ]
    y = 516
    for row_index, (item_id, service, owner, state) in enumerate(rows):
        if row_index == 1:
            draw.rectangle((60, y - 14, 572, y + 54), outline="#2563eb", width=3)  # intentionally offset focus ring.
        draw.rectangle((78, y - 1, 96, y + 17), outline="#94a3b8", width=2)
        if row_index == 1:
            draw.rectangle((82, y + 3, 92, y + 13), fill="#2563eb")
        draw.text((120, y - 4), item_id, fill="#151d2f", font=f14)
        draw.text((200, y - 4), service, fill="#151d2f", font=f14)
        draw.text((610, y - 4), owner, fill="#151d2f", font=f14)
        chip_fill = "#ffe9d1" if state == "blocked" else "#e8f7ee"
        chip_text = "#8a4f00" if state == "blocked" else "#166534"
        rounded(draw, (818, y - 9, 922, y + 22), 15, chip_fill, chip_fill)
        draw.text((841, y - 3), state, fill=chip_text, font=f12)
        y += 58

    # Timeline tabs.
    rounded(draw, (48, 770, 1020, 1030), 8, "#ffffff", "#d7dee9")
    draw.text((80, 800), "Release timeline", fill="#151d2f", font=f20)
    tabs = [("Plan", 86), ("Build", 246), ("Deploy", 430), ("Observe", 626)]
    for label, x in tabs:
        draw.text((x, 850), label, fill="#151d2f", font=f18)
    draw.line((408, 864, 736, 864), fill="#2458d8", width=5)  # crosses Deploy and Observe.
    draw.text((80, 938), "Published changes are waiting for review", fill="#536273", font=f15)

    # Right heatmap panel.
    rounded(draw, (1050, 370, 1548, 780), 8, "#ffffff", "#d7dee9")
    draw.text((1082, 398), "Risk heatmap", fill="#151d2f", font=f20)
    colors = ["#e9f5ff", "#b8dcff", "#80c2ff", "#4394ed", "#2458d8"]
    for i, color in enumerate(colors):
        draw.rectangle((1090 + i * 62, 450, 1138 + i * 62, 622), fill=color)
    draw.text((1082, 648), "Legend", fill="#536273", font=f14)
    draw.rectangle((1266, 648, 1282, 664), fill="#d923d9")
    draw.text((1352, 644), "Critical path", fill="#151d2f", font=f14)  # detached from swatch.

    # Workspace actions.
    rounded(draw, (1050, 820, 1548, 1030), 8, "#ffffff", "#d7dee9")
    draw.text((1082, 852), "Workspace actions", fill="#151d2f", font=f20)
    rounded(draw, (1294, 910, 1490, 958), 8, "#151d2f", "#151d2f")
    draw.text((1348, 924), "Sync now", fill="#ffffff", font=f16)
    rounded(draw, (1122, 882, 1492, 954), 8, "#fff4d6", "#f0b429")
    draw.text((1148, 898), "Import completed", fill="#5c4200", font=f16)
    draw.text((1148, 924), "3 warnings need review", fill="#5c4200", font=f13)

    img.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
