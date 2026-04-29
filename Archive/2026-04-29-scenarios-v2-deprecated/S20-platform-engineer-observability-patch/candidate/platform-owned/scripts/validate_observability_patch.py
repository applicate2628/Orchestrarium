#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Validate the S20 observability patch inside the bundle-local platform workspace."
    )
    parser.add_argument(
        "--emit-failure-ids",
        action="store_true",
        help="Print the current failure ids without failing the process.",
    )
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def parse_attribute_string(raw_value: str):
    parsed = {}
    for segment in raw_value.split(","):
        item = segment.strip()
        if not item:
            continue
        key, _, value = item.partition("=")
        parsed[key.strip()] = value.strip()
    return parsed


def collect_failures(workspace_root: Path):
    collector = load_json(workspace_root / "observability" / "collector-config.yaml")["collector"]
    deployment = load_json(workspace_root / "deploy" / "release-api-observability.yaml")["deployment"]
    contract = load_json(workspace_root / "fixtures" / "observability-contract.json")
    expected = contract["expected"]
    failures = []

    scrape_config = collector["receivers"]["prometheus"]["scrape_configs"][0]
    if scrape_config["metrics_path"] != expected["collector"]["metrics_path"]:
        failures.append("collector-metrics-path")

    if collector["pipelines"]["metrics"]["processors"] != expected["collector"]["processors"]:
        failures.append("collector-metrics-processors")

    if collector["exporters"]["otlphttp"]["endpoint"] != expected["collector"]["exporter_endpoint"]:
        failures.append("collector-exporter-endpoint")

    collector_attributes = collector["processors"]["resource"]["attributes"]
    for key, expected_value in expected["collector"]["resource_attributes"].items():
        if collector_attributes.get(key) != expected_value:
            failures.append("collector-resource-attributes")
            break

    annotations = deployment["podAnnotations"]
    if annotations.get("prometheus.io/path") != expected["deployment"]["prometheus_path"]:
        failures.append("deployment-prometheus-path")

    env = deployment["env"]
    if env.get("OTEL_EXPORTER_OTLP_ENDPOINT") != expected["deployment"]["otlp_endpoint"]:
        failures.append("deployment-otlp-endpoint")

    deployment_attributes = parse_attribute_string(env.get("OTEL_RESOURCE_ATTRIBUTES", ""))
    for key, expected_value in expected["deployment"]["resource_attributes"].items():
        if deployment_attributes.get(key) != expected_value:
            failures.append("deployment-resource-attributes")
            break

    return sorted(set(failures)), contract["required_validation_output"]


def main():
    args = parse_args()
    workspace_root = Path(__file__).resolve().parents[1]
    failures, required_output = collect_failures(workspace_root)

    if args.emit_failure_ids:
        for failure_id in failures:
            print(failure_id)
        return 0

    if failures:
        print("S20 validation FAIL")
        for failure_id in failures:
            print(failure_id)
        return 1

    print(required_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
