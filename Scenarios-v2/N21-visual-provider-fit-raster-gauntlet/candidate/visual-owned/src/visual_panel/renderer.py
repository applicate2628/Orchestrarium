from __future__ import annotations

RGB = tuple[int, int, int]
Frame = list[list[RGB]]

BACKGROUND: RGB = (17, 19, 24)
FOCUS_RING: RGB = (250, 204, 21)
ANNOTATION_GREEN: RGB = (34, 197, 94)
ADDITIVE_HIGHLIGHT: RGB = (30, 24, 0)

PALETTE: dict[int, RGB] = {
    -2: (29, 78, 216),
    -1: (147, 197, 253),
    0: (248, 250, 252),
    1: (252, 165, 165),
    2: (220, 38, 38),
}


def render_panel(spec: dict) -> Frame:
    width = int(spec["width"])
    height = int(spec["height"])
    background = _hex_to_rgb(spec.get("background", "#111318"))
    frame: Frame = [[background for _ in range(width)] for _ in range(height)]

    grid = spec["grid"]
    cell_size = int(grid["cell"])
    gap = int(grid["gap"])
    x0 = int(grid["x"])
    y0 = int(grid["y"])

    selected = spec.get("selected", {})
    selected_col = int(selected.get("col", -1))
    selected_row = int(selected.get("row", -1))

    for row_index, row in enumerate(spec["values"]):
        for col_index, raw_value in enumerate(row):
            value = 0 if raw_value is None else int(raw_value)
            color = PALETTE[value]
            left = x0 + col_index * (cell_size + gap)
            top = y0 + row_index * (cell_size + gap)
            _fill_rect(frame, left, top, cell_size, cell_size, color)
            if col_index == selected_col and row_index == selected_row:
                _fill_rect(frame, left, top, cell_size, cell_size, FOCUS_RING)

    legend = spec["legend"]
    legend_x = int(legend["x"])
    legend_y = int(legend["y"])
    legend_width = int(legend["width"])
    for index, value in enumerate([0, 1, 2, 2, 2]):
        _fill_rect(frame, legend_x, legend_y + index, legend_width, 1, PALETTE[value])

    return frame


def export_ppm(frame: Frame) -> str:
    height = len(frame)
    width = len(frame[0]) if frame else 0
    lines = ["P3", f"{height} {width}", "255"]
    for row in frame:
        channels: list[str] = []
        for red, green, blue in row:
            channels.extend([str(red), str(green), str(blue)])
        lines.append(" ".join(channels))
    return "\n".join(lines) + "\n"


def _fill_rect(frame: Frame, left: int, top: int, width: int, height: int, color: RGB) -> None:
    for y in range(max(0, top), min(len(frame), top + height)):
        for x in range(max(0, left), min(len(frame[y]), left + width)):
            frame[y][x] = color


def _hex_to_rgb(value: str) -> RGB:
    cleaned = value.strip().lstrip("#")
    if len(cleaned) != 6:
        raise ValueError(f"Expected #rrggbb color, got {value!r}")
    return (
        int(cleaned[0:2], 16),
        int(cleaned[2:4], 16),
        int(cleaned[4:6], 16),
    )
