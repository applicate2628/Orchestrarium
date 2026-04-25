#!/usr/bin/env python3

from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path


WIDTH = 2200
HEIGHT = 1600
IMAGE_ID = "N61-visual-localization-canvas-v1"

TARGETS = [
    ("red", 1876, 231, (239, 68, 68)),
    ("cyan", 342, 1274, (6, 182, 212)),
    ("lime", 1187, 822, (132, 204, 22)),
    ("magenta", 2011, 1439, (217, 70, 239)),
    ("amber", 742, 356, (245, 158, 11)),
    ("blue", 1544, 1129, (37, 99, 235)),
]

DECOYS = [
    (1842, 252, 9, 9, (239, 68, 68)),
    (384, 1215, 17, 9, (6, 182, 212)),
    (1231, 786, 9, 17, (132, 204, 22)),
    (1968, 1398, 17, 17, (217, 70, 239)),
    (778, 397, 9, 9, (245, 158, 11)),
    (1498, 1084, 17, 9, (37, 99, 235)),
    (215, 244, 13, 9, (239, 68, 68)),
    (2058, 288, 9, 13, (6, 182, 212)),
]

DIGITS = {
    "0": ("111", "101", "101", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "010", "010", "111"),
    "2": ("111", "001", "001", "111", "100", "100", "111"),
    "3": ("111", "001", "001", "111", "001", "001", "111"),
    "4": ("101", "101", "101", "111", "001", "001", "001"),
    "5": ("111", "100", "100", "111", "001", "001", "111"),
    "6": ("111", "100", "100", "111", "101", "101", "111"),
    "7": ("111", "001", "001", "010", "010", "010", "010"),
    "8": ("111", "101", "101", "111", "101", "101", "111"),
    "9": ("111", "101", "101", "111", "001", "001", "111"),
}


def put_pixel(frame: bytearray, x: int, y: int, color: tuple[int, int, int]) -> None:
    if 0 <= x < WIDTH and 0 <= y < HEIGHT:
        offset = (y * WIDTH + x) * 3
        frame[offset : offset + 3] = bytes(color)


def fill_rect(frame: bytearray, left: int, top: int, width: int, height: int, color: tuple[int, int, int]) -> None:
    for y in range(top, top + height):
        if y < 0 or y >= HEIGHT:
            continue
        for x in range(left, left + width):
            put_pixel(frame, x, y, color)


def stroke_rect(frame: bytearray, left: int, top: int, width: int, height: int, color: tuple[int, int, int]) -> None:
    for x in range(left, left + width):
        put_pixel(frame, x, top, color)
        put_pixel(frame, x, top + height - 1, color)
    for y in range(top, top + height):
        put_pixel(frame, left, y, color)
        put_pixel(frame, left + width - 1, y, color)


def draw_text(frame: bytearray, text: str, left: int, top: int, color: tuple[int, int, int], scale: int = 2) -> None:
    cursor = left
    for char in text:
        if char == " ":
            cursor += 4 * scale
            continue
        glyph = DIGITS.get(char)
        if not glyph:
            continue
        for gy, row in enumerate(glyph):
            for gx, bit in enumerate(row):
                if bit == "1":
                    fill_rect(frame, cursor + gx * scale, top + gy * scale, scale, scale, color)
        cursor += 4 * scale


def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    body = chunk_type + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def write_png(path: Path, frame: bytearray) -> None:
    rows = []
    stride = WIDTH * 3
    for y in range(HEIGHT):
        rows.append(b"\x00" + bytes(frame[y * stride : (y + 1) * stride]))
    payload = zlib.compress(b"".join(rows), level=9)
    png = b"\x89PNG\r\n\x1a\n"
    png += png_chunk(b"IHDR", struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0))
    png += png_chunk(b"IDAT", payload)
    png += png_chunk(b"IEND", b"")
    path.write_bytes(png)


def build_frame() -> bytearray:
    frame = bytearray([249, 250, 251] * WIDTH * HEIGHT)
    minor = (232, 236, 241)
    major = (190, 198, 210)
    axis = (54, 65, 82)
    label = (30, 41, 59)

    for x in range(0, WIDTH, 20):
        color = major if x % 100 == 0 else minor
        width = 2 if x % 100 == 0 else 1
        fill_rect(frame, x, 0, width, HEIGHT, color)
    for y in range(0, HEIGHT, 20):
        color = major if y % 100 == 0 else minor
        height = 2 if y % 100 == 0 else 1
        fill_rect(frame, 0, y, WIDTH, height, color)

    fill_rect(frame, 0, 0, WIDTH, 3, axis)
    fill_rect(frame, 0, 0, 3, HEIGHT, axis)
    for x in range(0, WIDTH + 1, 200):
        fill_rect(frame, x, 0, 2, 18, axis)
        draw_text(frame, str(x), min(x + 5, WIDTH - 50), 24, label, scale=2)
    for y in range(0, HEIGHT + 1, 200):
        fill_rect(frame, 0, y, 18, 2, axis)
        draw_text(frame, str(y), 24, min(y + 5, HEIGHT - 20), label, scale=2)

    for left, top, width, height, color in DECOYS:
        fill_rect(frame, left, top, width, height, color)
        stroke_rect(frame, left - 1, top - 1, width + 2, height + 2, (255, 255, 255))

    for _, center_x, center_y, color in TARGETS:
        fill_rect(frame, center_x - 6, center_y - 6, 13, 13, color)

    return frame


def write_oracle(path: Path) -> None:
    oracle = {
        "scenario_id": "N61",
        "image_id": IMAGE_ID,
        "image": {
            "path": "inputs/visual-localization-canvas.png",
            "width": WIDTH,
            "height": HEIGHT,
            "origin": "top-left",
            "grid": {"minor_px": 20, "major_px": 100},
        },
        "targets": [
            {
                "id": target_id,
                "center": {"x": x, "y": y},
                "size_px": 13,
                "color_rgb": list(color),
            }
            for target_id, x, y, color in TARGETS
        ],
        "thresholds": {
            "pass_mean_px": 5.0,
            "pass_max_px": 8.0,
        },
    }
    path.write_text(json.dumps(oracle, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[3]
    scenario_root = repo_root / "Scenarios-v2" / "N61-visual-pixel-localization-gauntlet"
    image_path = scenario_root / "inputs" / "visual-localization-canvas.png"
    oracle_path = scenario_root / "oracle" / "localization-oracle.json"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    oracle_path.parent.mkdir(parents=True, exist_ok=True)
    write_png(image_path, build_frame())
    write_oracle(oracle_path)
    print(f"wrote {image_path}")
    print(f"wrote {oracle_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
