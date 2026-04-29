from __future__ import annotations

from math import inf

Color = tuple[int, int, int, int]
Frame = list[list[Color]]


def render_scene(scene: dict) -> Frame:
    width = int(scene["width"])
    height = int(scene["height"])
    clear_color = _as_color(scene["clear_rgba"])

    color_buffer = [[clear_color for _ in range(width)] for _ in range(height)]
    depth_buffer = [[inf for _ in range(width)] for _ in range(height)]

    opaque_passes: list[dict] = []
    transparent_passes: list[dict] = []
    additive_passes: list[dict] = []

    for order, raw_draw in enumerate(scene["passes"]):
        draw = dict(raw_draw)
        draw["_order"] = order
        stage = draw["stage"]
        if stage == "opaque":
            opaque_passes.append(draw)
        elif stage == "transparent":
            transparent_passes.append(draw)
        elif stage == "additive":
            additive_passes.append(draw)
        else:
            raise ValueError(f"Unknown render stage: {stage}")

    opaque_passes.sort(key=lambda draw: (draw["depth"], draw["_order"]))
    transparent_passes.sort(key=lambda draw: (draw["depth"], draw["_order"]))
    additive_passes.sort(key=lambda draw: (draw["depth"], draw["_order"]))

    for draw in opaque_passes:
        _draw_rect(draw, color_buffer, depth_buffer, blend_mode="opaque", write_depth=True)

    for draw in transparent_passes:
        _draw_rect(draw, color_buffer, depth_buffer, blend_mode="alpha", write_depth=True)

    for draw in additive_passes:
        _draw_rect(draw, color_buffer, depth_buffer, blend_mode="alpha", write_depth=False)

    return color_buffer


def frame_to_hex_grid(frame: Frame) -> list[list[str]]:
    return [
        [f"#{r:02x}{g:02x}{b:02x}{a:02x}" for r, g, b, a in row]
        for row in frame
    ]


def _draw_rect(
    draw: dict,
    color_buffer: Frame,
    depth_buffer: list[list[float]],
    *,
    blend_mode: str,
    write_depth: bool,
) -> None:
    left = int(draw["x"])
    top = int(draw["y"])
    right = left + int(draw["width"])
    bottom = top + int(draw["height"])
    depth = float(draw["depth"])
    color = _as_color(draw["rgba"])

    y_start = max(0, top)
    y_stop = min(len(color_buffer), bottom)
    x_start = max(0, left)
    x_stop = min(len(color_buffer[0]), right)

    for y in range(y_start, y_stop):
        for x in range(x_start, x_stop):
            if depth > depth_buffer[y][x]:
                continue

            if blend_mode == "opaque":
                color_buffer[y][x] = color
            elif blend_mode == "alpha":
                color_buffer[y][x] = _alpha_over(color_buffer[y][x], color)
            elif blend_mode == "additive":
                color_buffer[y][x] = _additive(color_buffer[y][x], color)
            else:
                raise ValueError(f"Unknown blend mode: {blend_mode}")

            if write_depth:
                depth_buffer[y][x] = depth


def _alpha_over(dst: Color, src: Color) -> Color:
    alpha = src[3] / 255.0
    out_rgb = [
        round(src[channel] * alpha + dst[channel] * (1.0 - alpha))
        for channel in range(3)
    ]
    out_alpha = round(src[3] + dst[3] * (1.0 - alpha))
    return tuple(_clamp_channel(value) for value in (*out_rgb, out_alpha))


def _additive(dst: Color, src: Color) -> Color:
    alpha = src[3] / 255.0
    out_rgb = [
        min(255, dst[channel] + round(src[channel] * alpha))
        for channel in range(3)
    ]
    out_alpha = max(dst[3], src[3])
    return tuple(_clamp_channel(value) for value in (*out_rgb, out_alpha))


def _as_color(values: list[int] | tuple[int, int, int, int]) -> Color:
    if len(values) != 4:
        raise ValueError(f"Expected RGBA color with four channels, got {values!r}")
    return tuple(_clamp_channel(int(channel)) for channel in values)


def _clamp_channel(value: int) -> int:
    return max(0, min(255, int(value)))
