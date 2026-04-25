#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "Scenarios-v2" / "N68-actual-screenshot-visual-review-gauntlet" / "inputs" / "actual-screenshot.png"


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
    img = Image.new("RGB", (1280, 900), "#f4f6f8")
    draw = ImageDraw.Draw(img)

    f11 = font(11)
    f12 = font(12)
    f14 = font(14)
    f16 = font(16)
    f18 = font(18, True)
    f22 = font(22, True)
    f36 = font(36, True)

    # Decorative grid false-positive trap.
    for x in range(0, 1280, 40):
        draw.line((x, 0, x, 900), fill="#edf1f4", width=1)
    for y in range(0, 900, 40):
        draw.line((0, y, 1280, y), fill="#edf1f4", width=1)

    # Header.
    draw.rectangle((0, 0, 1280, 62), fill="#172033")
    draw.text((34, 18), "AuditGrid", fill="#ffffff", font=f22)
    draw.text((182, 24), "review workspace", fill="#aeb8c8", font=f14)

    # Search input defect: icon overlaps/clips placeholder.
    rounded(draw, (42, 72, 384, 112), 7, "#ffffff", "#cfd7e3")
    draw.ellipse((59, 85, 73, 99), outline="#41516b", width=2)
    draw.line((70, 96, 82, 108), fill="#41516b", width=3)
    draw.rectangle((76, 76, 247, 108), fill="#ffffff")
    draw.text((86, 84), "Search incidents", fill="#526070", font=f16)
    draw.line((82, 80, 82, 106), fill="#172033", width=2)

    # Right actions.
    rounded(draw, (914, 72, 1002, 112), 7, "#f2f4f7", "#cfd7e3")
    draw.text((937, 84), "Export", fill="#a5afbd", font=f16)  # disabled false-positive trap.
    rounded(draw, (1026, 72, 1164, 112), 7, "#2364d2", "#1d55b5")
    draw.text((1053, 84), "Run audit", fill="#ffffff", font=f16)
    draw.ellipse((1053, 82, 1073, 102), outline="#ffffff", width=4)
    draw.arc((1053, 82, 1073, 102), 40, 270, fill="#2364d2", width=5)

    # Cards.
    rounded(draw, (42, 148, 408, 286), 8, "#ffffff", "#d5dde8")
    draw.text((66, 170), "Risk score", fill="#526070", font=f16)
    draw.text((66, 198), "99.7%", fill="#172033", font=f36)
    draw.rectangle((332, 188, 409, 246), fill="#ffffff")  # clips the value on purpose.
    draw.line((332, 188, 332, 246), fill="#b8c2d0", width=1)
    draw.text((66, 250), "Compared to baseline", fill="#8994a4", font=f12)

    rounded(draw, (438, 148, 804, 286), 8, "#ffffff", "#d5dde8")
    draw.text((462, 170), "Service status", fill="#526070", font=f16)
    draw.text((462, 204), "Payment core", fill="#172033", font=f22)
    rounded(draw, (726, 196, 850, 234), 18, "#35d07f", "#35d07f")
    draw.text((750, 207), "Healthy", fill="#36ce81", font=f14)  # low contrast on purpose.
    draw.text((462, 250), "Muted timestamp: 08:42 UTC", fill="#9aa5b5", font=f12)  # false-positive trap.

    rounded(draw, (834, 148, 1218, 286), 8, "#ffffff", "#d5dde8")
    draw.text((858, 170), "Deploy trend", fill="#526070", font=f16)
    draw.line((876, 242, 927, 210), fill="#2364d2", width=4)
    draw.line((927, 210, 983, 229), fill="#2364d2", width=4)
    draw.line((983, 229, 1039, 187), fill="#2364d2", width=4)
    draw.line((1039, 187, 1117, 222), fill="#2364d2", width=4)
    draw.rectangle((947, 531, 960, 544), fill="#d923d9")

    # Table.
    rounded(draw, (42, 320, 804, 620), 8, "#ffffff", "#d5dde8")
    draw.text((66, 342), "Incident queue", fill="#172033", font=f18)
    draw.text((66, 388), "ID", fill="#526070", font=f14)
    draw.text((176, 388), "Service", fill="#526070", font=f14)
    draw.text((506, 388), "Owner", fill="#526070", font=f14)
    draw.polygon([(728, 392), (742, 392), (735, 404)], fill="#172033")  # overlaps Owner header.
    draw.line((42, 418, 804, 418), fill="#e3e8ef", width=1)
    rows = [
        ("AG-1904", "Payment settlement", "Mira", "blocked"),
        ("AG-1905", "Webhook retries", "Ivan", "ready"),
        ("AG-1906", "Balance export", "Nora", "ready"),
    ]
    y = 444
    for item_id, service, owner, state in rows:
        draw.text((66, y), item_id, fill="#172033", font=f14)
        draw.text((176, y), service, fill="#172033", font=f14)
        draw.text((506, y), owner, fill="#172033", font=f14)
        chip_fill = "#ffe9d1" if state == "blocked" else "#e8f7ee"
        chip_text = "#8a4f00" if state == "blocked" else "#166534"
        rounded(draw, (664, y - 4, 756, y + 24), 14, chip_fill, chip_fill)
        draw.text((681, y + 1), state, fill=chip_text, font=f12)
        y += 56

    # Timeline tabs.
    rounded(draw, (42, 646, 804, 810), 8, "#ffffff", "#d5dde8")
    draw.text((66, 668), "Release timeline", fill="#172033", font=f18)
    tabs = [("Plan", 72), ("Build", 196), ("Deploy", 336), ("Observe", 494)]
    for label, x in tabs:
        draw.text((x, 718), label, fill="#172033", font=f16)
    draw.line((337, 728, 624, 728), fill="#2364d2", width=5)  # crosses Deploy and Observe.

    # Side panel and legend defect.
    rounded(draw, (834, 320, 1218, 700), 8, "#ffffff", "#d5dde8")
    draw.text((858, 342), "Risk heatmap", fill="#172033", font=f18)
    colors = ["#e9f5ff", "#b8dcff", "#80c2ff", "#4394ed", "#2364d2"]
    for i, color in enumerate(colors):
        draw.rectangle((872 + i * 48, 394, 908 + i * 48, 586), fill=color)
    draw.text((858, 528), "Legend", fill="#526070", font=f14)
    draw.rectangle((960, 542, 972, 554), fill="#d923d9")
    draw.text((1018, 538), "Critical path", fill="#172033", font=f14)  # detached from swatch.

    # Toast overlaps Sync now button.
    rounded(draw, (834, 730, 1218, 836), 8, "#ffffff", "#d5dde8")
    draw.text((858, 754), "Workspace actions", fill="#172033", font=f18)
    rounded(draw, (1010, 772, 1166, 814), 7, "#172033", "#172033")
    draw.text((1043, 784), "Sync now", fill="#ffffff", font=f16)
    rounded(draw, (879, 742, 1169, 808), 8, "#fff4d6", "#f0b429")
    draw.text((902, 756), "Import completed", fill="#5c4200", font=f16)
    draw.text((902, 780), "3 warnings need review", fill="#5c4200", font=f12)

    img.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
