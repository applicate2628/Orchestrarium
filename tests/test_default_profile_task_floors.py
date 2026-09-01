#!/usr/bin/env python3
"""Regression checks for executable default role profiles versus task floors."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "shared" / "role-routing-policy.v1.json"


def test_every_eligible_role_default_meets_its_task_floor() -> None:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    model_index = {
        value: index for index, value in enumerate(policy["modelTierOrder"])
    }
    effort_index = {
        value: index for index, value in enumerate(policy["effortOrder"])
    }

    failures: list[str] = []
    for task_name, eligible_roles in policy["taskRoleEligibility"].items():
        task = policy["taskClasses"][task_name]
        for role_name in eligible_roles:
            role = policy["roles"][role_name]
            profile_name = role["defaultProfile"]
            profile = policy["profiles"][profile_name]
            if (
                model_index[profile["modelTier"]]
                < model_index[task["requiredModelTier"]]
                or effort_index[profile["effort"]]
                < effort_index[task["requiredEffort"]]
            ):
                failures.append(f"{task_name}:{role_name}:{profile_name}")

    assert failures == []


def test_reviewed_roles_use_floor_satisfying_defaults() -> None:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    assert policy["roles"]["security-engineer"]["defaultProfile"] == "frontier-xhigh"
    assert policy["roles"]["worker"]["defaultProfile"] == "frontier-high"
    assert policy["roles"]["platform-engineer"]["defaultProfile"] == "frontier-high"
