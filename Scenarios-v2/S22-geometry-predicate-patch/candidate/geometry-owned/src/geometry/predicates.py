from __future__ import annotations

from typing import Tuple

Point = Tuple[float, float]
DEFAULT_EPSILON = 1e-9


def signed_area2(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def orientation(a: Point, b: Point, c: Point, eps: float = DEFAULT_EPSILON) -> int:
    det = signed_area2(a, b, c)
    if abs(det) <= eps:
        return 0
    return 1 if det > 0.0 else -1


def _between(value: float, left: float, right: float) -> bool:
    lower = min(left, right)
    upper = max(left, right)
    return lower <= value <= upper


def on_segment(a: Point, b: Point, p: Point, eps: float = DEFAULT_EPSILON) -> bool:
    if orientation(a, b, p, eps=eps) != 0:
        return False
    return _between(p[0], a[0], b[0]) and _between(p[1], a[1], b[1])


def segments_intersect(
    a1: Point,
    a2: Point,
    b1: Point,
    b2: Point,
    eps: float = DEFAULT_EPSILON,
) -> bool:
    o1 = orientation(a1, a2, b1, eps=eps)
    o2 = orientation(a1, a2, b2, eps=eps)
    o3 = orientation(b1, b2, a1, eps=eps)
    o4 = orientation(b1, b2, a2, eps=eps)

    if o1 == 0 and on_segment(a1, a2, b1, eps=eps):
        return True
    if o2 == 0 and on_segment(a1, a2, b2, eps=eps):
        return True
    if o3 == 0 and on_segment(b1, b2, a1, eps=eps):
        return True
    if o4 == 0 and on_segment(b1, b2, a2, eps=eps):
        return True

    return o1 != o2 and o3 != o4
