"""Deterministic paired process-supervision benchmark protocol."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence


@dataclass(frozen=True)
class BenchmarkPairV1:
    one_based_index: int
    expected_order: str
    observed_order: str
    direct_seconds: float
    supervised_seconds: float
    signed_delta_seconds: float

    def to_dict(self) -> dict[str, float | int | str]:
        return {
            "oneBasedIndex": self.one_based_index,
            "expectedOrder": self.expected_order,
            "observedOrder": self.observed_order,
            "directSeconds": self.direct_seconds,
            "supervisedSeconds": self.supervised_seconds,
            "signedDeltaSeconds": self.signed_delta_seconds,
        }


@dataclass(frozen=True)
class BenchmarkDescriptiveV1:
    minimum: float
    maximum: float
    median: float

    def to_dict(self) -> dict[str, float]:
        return {"min": self.minimum, "max": self.maximum, "median": self.median}


@dataclass(frozen=True, init=False)
class BenchmarkEvidenceV1:
    scenario_id: str
    cohort_kind: str
    pairs: tuple[BenchmarkPairV1, ...]

    @property
    def descriptive(self) -> BenchmarkDescriptiveV1:
        deltas = [item.signed_delta_seconds for item in self.pairs]
        if not deltas:
            raise ValueError("benchmark evidence has no pairs")
        return BenchmarkDescriptiveV1(
            min(deltas), max(deltas), float(statistics.median(deltas))
        )

    @property
    def production_p95(self) -> float | None:
        if self.cohort_kind != "production":
            return None
        return _nearest_rank(
            [item.signed_delta_seconds for item in self.pairs], 0.95
        )

    @property
    def production_verdict(self) -> bool | None:
        p95 = self.production_p95
        if p95 is None:
            return None
        return self.descriptive.median <= 0.250 and p95 <= 0.500

    @classmethod
    def build(
        cls,
        scenario_id: str,
        cohort_kind: str,
        pairs: Sequence[Mapping[str, float | int | str]],
    ) -> "BenchmarkEvidenceV1":
        if not scenario_id or cohort_kind not in {"development", "production"}:
            raise ValueError("benchmark identity")
        if cohort_kind == "development" and len(pairs) != 5:
            raise ValueError("development evidence requires exactly 5 pairs")
        if cohort_kind == "production" and len(pairs) < 40:
            raise ValueError("production evidence requires at least 40 pairs")
        required = {
            "oneBasedIndex",
            "expectedOrder",
            "observedOrder",
            "directSeconds",
            "supervisedSeconds",
            "signedDeltaSeconds",
        }
        validated: list[BenchmarkPairV1] = []
        for expected_index, raw in enumerate(pairs, 1):
            if set(raw) != required or raw["oneBasedIndex"] != expected_index:
                raise ValueError("missing, duplicate, or non-contiguous pair")
            expected_order = (
                "direct-supervised"
                if expected_index % 2
                else "supervised-direct"
            )
            if (
                raw["expectedOrder"] != expected_order
                or raw["observedOrder"] != expected_order
            ):
                raise ValueError("pair order bias")
            direct = raw["directSeconds"]
            supervised = raw["supervisedSeconds"]
            supplied_delta = raw["signedDeltaSeconds"]
            if any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                for value in (direct, supervised, supplied_delta)
            ):
                raise ValueError("non-finite benchmark value")
            direct_value = float(direct)
            supervised_value = float(supervised)
            if direct_value < 0 or supervised_value < 0:
                raise ValueError("negative raw duration")
            derived = supervised_value - direct_value
            if not math.isclose(
                float(supplied_delta), derived, rel_tol=0.0, abs_tol=1e-12
            ):
                raise ValueError("signed delta mismatch")
            validated.append(
                BenchmarkPairV1(
                    expected_index,
                    expected_order,
                    expected_order,
                    direct_value,
                    supervised_value,
                    derived,
                )
            )
        instance = object.__new__(cls)
        object.__setattr__(instance, "scenario_id", scenario_id)
        object.__setattr__(instance, "cohort_kind", cohort_kind)
        object.__setattr__(instance, "pairs", tuple(validated))
        return instance

    def to_dict(self) -> dict[str, object]:
        validated = type(self).build(
            self.scenario_id,
            self.cohort_kind,
            [item.to_dict() for item in self.pairs],
        )
        result: dict[str, object] = {
            "schemaVersion": 1,
            "scenarioId": validated.scenario_id,
            "cohortKind": validated.cohort_kind,
            "pairCount": len(validated.pairs),
            "pairs": [item.to_dict() for item in validated.pairs],
            "descriptive": validated.descriptive.to_dict(),
        }
        if validated.cohort_kind == "production":
            result["productionP95"] = validated.production_p95
            result["productionVerdict"] = validated.production_verdict
        return result


def build_pairs(
    count: int,
    *,
    direct: Callable[[int], float],
    supervised: Callable[[int], float],
) -> list[dict[str, float | str]]:
    if count <= 0:
        raise ValueError("pair count must be positive")
    pairs: list[dict[str, float | str]] = []
    for index in range(count):
        if index % 2 == 0:
            direct_ms = float(direct(index))
            supervised_ms = float(supervised(index))
            order = "direct-supervised"
        else:
            supervised_ms = float(supervised(index))
            direct_ms = float(direct(index))
            order = "supervised-direct"
        pairs.append(
            {
                "order": order,
                "directMs": direct_ms,
                "supervisedMs": supervised_ms,
                "signedDeltaMs": supervised_ms - direct_ms,
            }
        )
    return pairs


def _nearest_rank(values: Sequence[float], percentile: float) -> float:
    if not values:
        raise ValueError("at least one sample is required")
    ordered = sorted(float(value) for value in values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def summarize_pairs(
    pairs: Sequence[Mapping[str, float | str]],
    *,
    production: bool,
) -> dict[str, float | int | bool | str]:
    raw = []
    for index, item in enumerate(pairs, 1):
        order = "direct-supervised" if index % 2 else "supervised-direct"
        raw.append(
            {
                "oneBasedIndex": index,
                "expectedOrder": order,
                "observedOrder": item["order"],
                "directSeconds": float(item["directMs"]) / 1000.0,
                "supervisedSeconds": float(item["supervisedMs"]) / 1000.0,
                "signedDeltaSeconds": float(item["signedDeltaMs"]) / 1000.0,
            }
        )
    evidence = BenchmarkEvidenceV1.build(
        "compat", "production" if production else "development", raw
    ).to_dict()
    return evidence


__all__ = [
    "BenchmarkDescriptiveV1",
    "BenchmarkEvidenceV1",
    "BenchmarkPairV1",
    "build_pairs",
    "summarize_pairs",
]
