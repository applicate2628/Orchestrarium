from __future__ import annotations

import math
from decimal import Decimal
from typing import Any

from .normalization import canonical_item_key, normalize_scalar


def _as_number(value: Decimal) -> int | float:
    if value == value.to_integral():
        return int(value)
    return float(value)


def weighted_f1(tp: float | Decimal, fp: float | Decimal, fn: float | Decimal) -> dict[str, float | int]:
    tp_d, fp_d, fn_d = Decimal(str(tp)), Decimal(str(fp)), Decimal(str(fn))
    precision_den = tp_d + fp_d
    recall_den = tp_d + fn_d
    if precision_den == 0 and recall_den == 0:
        precision = recall = f1 = Decimal(1)
    else:
        precision = tp_d / precision_den if precision_den else Decimal(0)
        recall = tp_d / recall_den if recall_den else Decimal(0)
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else Decimal(0)
    return {
        "precision": _as_number(precision),
        "recall": _as_number(recall),
        "f1": _as_number(f1),
        "tp": _as_number(tp_d),
        "fp": _as_number(fp_d),
        "fn": _as_number(fn_d),
    }


def numeric_credit(
    actual: Any,
    expected: Any,
    actual_unit: Any,
    expected_unit: Any,
    full_tolerance: Any,
    zero_tolerance: Any,
) -> float | int:
    try:
        actual_f = float(actual)
        expected_f = float(expected)
        full_f = float(full_tolerance)
        zero_f = float(zero_tolerance)
    except (TypeError, ValueError):
        return 0
    if not all(math.isfinite(value) for value in (actual_f, expected_f, full_f, zero_f)):
        return 0
    if normalize_scalar(actual_unit, casefold=True) != normalize_scalar(expected_unit, casefold=True):
        return 0
    error = abs(actual_f - expected_f)
    if error <= full_f:
        return 1
    if error >= zero_f:
        return 0
    return (zero_f - error) / (zero_f - full_f)


def _set_f1(expected: list[Any], actual: list[Any], *, casefold: bool, aliases: dict[str, str] | None) -> dict:
    expected_set = {normalize_scalar(item, casefold=casefold, aliases=aliases) for item in expected}
    actual_set = {normalize_scalar(item, casefold=casefold, aliases=aliases) for item in actual}
    return weighted_f1(
        tp=len(expected_set & actual_set),
        fp=len(actual_set - expected_set),
        fn=len(expected_set - actual_set),
    )


def source_ranking_credit(
    expected: list[Any],
    actual: list[Any],
    *,
    casefold: bool = False,
    aliases: dict[str, str] | None = None,
) -> dict[str, float | int]:
    exp = [normalize_scalar(item, casefold=casefold, aliases=aliases) for item in expected]
    act = [normalize_scalar(item, casefold=casefold, aliases=aliases) for item in actual]
    set_result = _set_f1(exp, act, casefold=False, aliases=None)
    positions = {item: index for index, item in enumerate(act)}
    pair_total = len(exp) * (len(exp) - 1) // 2
    pair_hits = 0
    for left in range(len(exp)):
        for right in range(left + 1, len(exp)):
            if exp[left] in positions and exp[right] in positions and positions[exp[left]] < positions[exp[right]]:
                pair_hits += 1
    pairwise = pair_hits / pair_total if pair_total else (1 if not exp and not act else 0)
    credit = 0.4 * float(set_result["f1"]) + 0.6 * pairwise
    return {
        "credit": credit,
        "set_f1": set_result["f1"],
        "pairwise_accuracy": pairwise,
        "correct_pairs": pair_hits,
        "total_pairs": pair_total,
    }


def _hungarian_max(weights: list[list[Decimal]]) -> list[tuple[int, int]]:
    size = len(weights)
    if size == 0:
        return []
    costs = [[-value for value in row] for row in weights]
    u = [Decimal(0)] * (size + 1)
    v = [Decimal(0)] * (size + 1)
    p = [0] * (size + 1)
    way = [0] * (size + 1)
    infinity = Decimal("Infinity")
    for row in range(1, size + 1):
        p[0] = row
        column0 = 0
        minimum = [infinity] * (size + 1)
        used = [False] * (size + 1)
        while True:
            used[column0] = True
            row0 = p[column0]
            delta = infinity
            column1 = 0
            for column in range(1, size + 1):
                if used[column]:
                    continue
                current = costs[row0 - 1][column - 1] - u[row0] - v[column]
                if current < minimum[column]:
                    minimum[column] = current
                    way[column] = column0
                if minimum[column] < delta:
                    delta = minimum[column]
                    column1 = column
            for column in range(size + 1):
                if used[column]:
                    u[p[column]] += delta
                    v[column] -= delta
                else:
                    minimum[column] -= delta
            column0 = column1
            if p[column0] == 0:
                break
        while True:
            column1 = way[column0]
            p[column0] = p[column1]
            column0 = column1
            if column0 == 0:
                break
    return sorted((p[column] - 1, column - 1) for column in range(1, size + 1) if p[column])


def findings_f1(
    expected: list[dict[str, Any]],
    reported: list[dict[str, Any]],
    *,
    match_fields: list[str],
    severity_weights: dict[str, int | float],
    severity_field: str = "severity",
    casefold_fields: list[str] | None = None,
    aliases: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    casefold_set = set(casefold_fields or [])
    aliases = aliases or {}
    expected_sorted = sorted(expected, key=canonical_item_key)
    reported_sorted = sorted(reported, key=canonical_item_key)
    size = max(len(expected_sorted), len(reported_sorted))
    weights = [[Decimal(0) for _ in range(size)] for _ in range(size)]
    compatible: set[tuple[int, int]] = set()

    def normalized(item: dict[str, Any], field: str) -> Any:
        return normalize_scalar(
            item.get(field),
            casefold=field in casefold_set,
            aliases=aliases.get(field),
        )

    def normalized_severity(item: dict[str, Any]) -> Any:
        return normalize_scalar(
            item.get(severity_field),
            casefold=True,
            aliases=aliases.get(severity_field),
        )

    for expected_index, target in enumerate(expected_sorted):
        severity = normalize_scalar(target.get(severity_field), casefold=True)
        target_weight = Decimal(str(severity_weights.get(str(severity), 1)))
        for reported_index, finding in enumerate(reported_sorted):
            if normalized_severity(target) == normalized_severity(finding) and all(
                normalized(target, field) == normalized(finding, field) for field in match_fields
            ):
                compatible.add((expected_index, reported_index))
                weights[expected_index][reported_index] = target_weight

    assignment = _hungarian_max(weights)
    matches = [(left, right) for left, right in assignment if (left, right) in compatible]
    matched_expected = {left for left, _ in matches}
    matched_reported = {right for _, right in matches}

    tp = sum(
        Decimal(str(severity_weights.get(str(normalize_scalar(expected_sorted[left].get(severity_field), casefold=True)), 1)))
        for left in matched_expected
    )
    fn = sum(
        Decimal(str(severity_weights.get(str(normalize_scalar(item.get(severity_field), casefold=True)), 1)))
        for index, item in enumerate(expected_sorted)
        if index not in matched_expected
    )
    fp = sum(
        Decimal(str(severity_weights.get(str(normalize_scalar(item.get(severity_field), casefold=True)), 1)))
        for index, item in enumerate(reported_sorted)
        if index not in matched_reported
    )
    result = weighted_f1(tp, fp, fn)
    result.update(
        {
            "matched_count": len(matches),
            "unmatched_expected_count": len(expected_sorted) - len(matches),
            "unmatched_reported_count": len(reported_sorted) - len(matches),
            "matches": [
                {
                    "expected_id": expected_sorted[left].get("id", canonical_item_key(expected_sorted[left])),
                    "reported_id": reported_sorted[right].get("id", canonical_item_key(reported_sorted[right])),
                }
                for left, right in matches
            ],
        }
    )
    return result


def set_f1(
    expected: list[Any],
    actual: list[Any],
    *,
    casefold: bool = False,
    aliases: dict[str, str] | None = None,
) -> dict[str, float | int]:
    return _set_f1(expected, actual, casefold=casefold, aliases=aliases)
