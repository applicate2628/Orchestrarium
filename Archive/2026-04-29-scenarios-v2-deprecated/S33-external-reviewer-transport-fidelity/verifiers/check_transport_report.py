import argparse
import json
import re
import sys
from pathlib import Path


PLACEHOLDER_PREFIX = "<fill"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def find_label(report_text: str, label: str) -> str | None:
    pattern = rf"^{re.escape(label)}:\s*(.+)$"
    match = re.search(pattern, report_text, re.MULTILINE)
    return match.group(1).strip() if match else None


def collect_top_level_yaml_keys(yaml_text: str) -> list[str]:
    keys = []
    for line in yaml_text.splitlines():
        if not line or line.startswith(" ") or line.startswith("-"):
            continue
        match = re.match(r"^([A-Za-z_]+):", line)
        if match:
            keys.append(match.group(1))
    return keys


def find_yaml_scalar(yaml_text: str, key: str) -> str | None:
    match = re.search(rf"^{re.escape(key)}:\s*(.+)$", yaml_text, re.MULTILINE)
    if not match:
        return None
    return match.group(1).strip().strip('"')


def check_bundle_shape(bundle_root: Path, errors: list[str]) -> None:
    required_entries = [
        bundle_root / "scenario.yaml",
        bundle_root / "README.md",
        bundle_root / "inputs",
        bundle_root / "candidate",
        bundle_root / "oracle",
        bundle_root / "verifiers",
    ]
    for path in required_entries:
        if not path.exists():
            errors.append(f"Missing required bundle entry: {path.relative_to(bundle_root)}")


def check_scenario_yaml(bundle_root: Path, contract: dict, errors: list[str]) -> None:
    yaml_path = bundle_root / "scenario.yaml"
    yaml_text = read_text(yaml_path)
    keys = collect_top_level_yaml_keys(yaml_text)
    expected_keys = contract["required_scenario_keys"]
    if keys != expected_keys:
        errors.append(
            "scenario.yaml top-level keys do not match the required contract fields exactly: "
            f"expected {expected_keys}, found {keys}"
        )

    for key, expected_value in contract["expected_scenario_values"].items():
        actual_value = find_yaml_scalar(yaml_text, key)
        if actual_value != expected_value:
            errors.append(
                f"scenario.yaml value mismatch for {key!r}: expected {expected_value!r}, found {actual_value!r}"
            )

    if "candidate/transport-execution-report.md" not in yaml_text:
        errors.append("scenario.yaml missing the allowed change surface for the transport report")
    if "external-transport" not in yaml_text:
        errors.append("scenario.yaml missing overlay flag external-transport")


def check_report_sections(report_text: str, contract: dict, errors: list[str]) -> None:
    for section in contract["required_sections"]:
        if section not in report_text:
            errors.append(f"Missing required report section: {section}")


def check_report_labels(report_text: str, contract: dict, errors: list[str], completed: bool) -> None:
    for label in contract["required_labels"]:
        value = find_label(report_text, label)
        if value is None:
            errors.append(f"Missing required report label: {label}")
            continue
        if not value:
            errors.append(f"Empty value for report label: {label}")
            continue
        if completed and value.startswith(PLACEHOLDER_PREFIX):
            errors.append(f"Placeholder value still present for completed report label: {label}")


def check_completed_report(report_text: str, contract: dict, errors: list[str]) -> None:
    for label, expected_value in contract["expected_report_values"].items():
        actual_value = find_label(report_text, label)
        if actual_value != expected_value:
            errors.append(
                f"Completed report mismatch for {label!r}: expected {expected_value!r}, found {actual_value!r}"
            )

    for snippet in contract["required_fact_snippets"]:
        if snippet not in report_text:
            errors.append(f"Completed report missing required fact snippet: {snippet}")

    for snippet in contract["required_scope_snippets"]:
        if snippet not in report_text:
            errors.append(f"Completed report missing required scope snippet: {snippet}")

    lowered = report_text.lower()
    for snippet in contract["prohibited_snippets"]:
        if snippet.lower() in lowered:
            errors.append(f"Completed report contains prohibited snippet: {snippet}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("template", "completed"),
        default="template",
        help="template validates the seeded bundle; completed validates a filled report against the oracle",
    )
    args = parser.parse_args()

    bundle_root = Path(__file__).resolve().parent.parent
    contract_path = bundle_root / "oracle" / "provenance-contract.json"
    report_path = bundle_root / "candidate" / "transport-execution-report.md"

    errors: list[str] = []
    contract = json.loads(read_text(contract_path))

    check_bundle_shape(bundle_root, errors)
    check_scenario_yaml(bundle_root, contract, errors)

    report_text = read_text(report_path)
    check_report_sections(report_text, contract, errors)
    check_report_labels(report_text, contract, errors, completed=args.mode == "completed")

    if args.mode == "completed":
        check_completed_report(report_text, contract, errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print(f"PASS: {args.mode} verification succeeded for {bundle_root.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
