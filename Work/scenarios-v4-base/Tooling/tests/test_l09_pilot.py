from __future__ import annotations

import json
import re
import sys
import unittest
from decimal import Decimal
from pathlib import Path
from typing import Any

import jsonschema
import yaml


PACK_ROOT = Path(__file__).resolve().parents[2]
TOOLING_ROOT = PACK_ROOT / "Tooling"
sys.path.insert(0, str(TOOLING_ROOT))

from v4_rubric.contracts import validate_rubric  # noqa: E402


COMPETENT_DERIVED_PROBE = "competent-derived"

LEGACY_EXPECTED_PROBES = (
    "reference",
    "vacuous",
    "decoy",
    "wrong-substance",
    "one-atom-deletion",
    "semantic-deletion-20pct",
    "alternate-valid",
    "paraphrase-reordered",
    "extra-false-finding",
    "forbidden-positive-claim",
    "defensible-alternate",
)

EXPECTED_PROBES = LEGACY_EXPECTED_PROBES + (COMPETENT_DERIVED_PROBE,)

PILOT_ROOTS = {
    "V4L09B-pre-pr-review": {
        "form": "base",
        "component_profile": {
            "findings": 17,
            "binding": 8,
            "decoys": 16,
            "scope": 3,
            "merge_clearance": 8,
            "severity": 23,
            "actions": 23,
            "integrity_or_schema": 2,
        },
        "source_id_pattern": r"B-CARD-\d{3}",
        "expected_findings": {
            "B01-cache-read-aliasing": {
                "file": "cache/store.py",
                "symbol": "Cache.get",
                "class": "correctness-cache",
                "source_ids": ["B-CARD-101", "B-CARD-102"],
                "proof_files": [
                    "B01-cache-read-aliasing/failing-test.py",
                    "B01-cache-read-aliasing/transcript.txt",
                ],
            },
            "B02-retry-budget": {
                "file": "workers/retry.py",
                "symbol": "RetryWorker.run",
                "class": "reliability-retry",
                "source_ids": ["B-CARD-201", "B-CARD-202"],
                "proof_files": [
                    "B02-retry-budget/failing-test.py",
                    "B02-retry-budget/transcript.txt",
                ],
            },
            "B03-query-filtering": {
                "file": "items/repository.py",
                "symbol": "list_items",
                "class": "performance-query",
                "source_ids": ["B-CARD-301", "B-CARD-302"],
                "proof_files": ["B03-query-filtering/trace-invariant.json"],
            },
            "B04-token-expiry": {
                "file": "auth/token.py",
                "symbol": "parse_token",
                "class": "security-token",
                "source_ids": ["B-CARD-401", "B-CARD-402"],
                "proof_files": [
                    "B04-token-expiry/failing-test.py",
                    "B04-token-expiry/transcript.txt",
                ],
            },
        },
        "expected_safe": {
            "B05-log-order-safe": {
                "source_ids": ["B-CARD-501", "B-CARD-502"],
                "proof_files": ["B05-log-order-safe/passing-proof.txt"],
            },
            "B06-doc-only-safe": {
                "source_ids": ["B-CARD-601", "B-CARD-602"],
                "proof_files": ["B06-doc-only-safe/passing-proof.txt"],
            },
        },
    },
    "V4L09F-pre-pr-review": {
        "form": "frontier",
        "component_profile": {
            "findings": 17,
            "binding": 8,
            "special_reasoning": 14,
            "numeric": 9,
            "decoys": 17,
            "severity_action": 20,
            "scope_gate": 15,
        },
        "source_id_pattern": r"F-CARD-\d{3}",
        "expected_findings": {
            "F01-out-of-order-ack": {
                "file": "ui/save_state.py",
                "symbol": "apply_ack",
                "class": "correctness-state",
                "source_ids": ["F-CARD-101", "F-CARD-102", "F-CARD-103"],
                "proof_files": [
                    "F01-out-of-order-ack/failing-test.py",
                    "F01-out-of-order-ack/transcript.txt",
                ],
            },
            "F02-retry-depends-on-state": {
                "file": "ui/save_queue.py",
                "symbol": "schedule_retry",
                "class": "reliability-retry",
                "source_ids": ["F-CARD-201", "F-CARD-202"],
                "depends_on": "F01-out-of-order-ack",
                "proof_files": ["F02-retry-depends-on-state/trace-invariant.json"],
            },
            "F03-cross-diff-auth": {
                "file": "auth/audience.py",
                "symbol": "normalize_audience",
                "class": "security-auth",
                "source_ids": ["F-CARD-301", "F-CARD-302"],
                "cross_diff_source_ids": ["F-CARD-301", "F-CARD-302"],
                "proof_files": [
                    "F03-cross-diff-auth/failing-integration-test.py",
                    "F03-cross-diff-auth/transcript.txt",
                ],
            },
            "F04-feed-permission-profile": {
                "file": "feed/query.py",
                "symbol": "load_page",
                "class": "performance-query",
                "source_ids": ["F-CARD-401", "F-CARD-402"],
                "proof_files": [
                    "F04-feed-permission-profile/profile-threshold.json",
                    "F04-feed-permission-profile/raw-count.txt",
                ],
            },
        },
        "expected_safe": {
            "F05-fixture-name-safe": {
                "source_ids": ["F-CARD-501", "F-CARD-502"],
                "proof_files": ["F05-fixture-name-safe/passing-proof.txt"],
            },
            "F06-log-sampling-safe": {
                "source_ids": ["F-CARD-601", "F-CARD-602"],
                "proof_files": ["F06-log-sampling-safe/passing-proof.txt"],
            },
        },
        "numeric_target": {
            "id": "permission_lookup_calls",
            "candidate_path": "profile_measurements.permission_lookup_calls",
            "expected": 1201,
            "unit": "calls",
            "full_tolerance": 0,
            "zero_tolerance": 1176,
            "proof_files": [
                "F04-feed-permission-profile/profile-threshold.json",
                "F04-feed-permission-profile/raw-count.txt",
            ],
        },
    },
}

EXPECTED_BUNDLE_FILES = (
    "README.md",
    "scenario.yaml",
    "inputs/task.md",
    "inputs/output-schema.json",
    "inputs/sources/source-cards.md",
    "candidate/README.md",
    "oracle/rubric.json",
    "oracle/reference-answer.json",
    "verifiers/score.py",
)

FORBIDDEN_METADATA_TOKENS = (
    "expected-winner",
    "expected_winner",
    "expected winner",
    "expected-rank",
    "expected_rank",
    "expected rank",
    "desired-ranking",
    "desired_ranking",
    "desired ranking",
    "target-ranking",
    "target_ranking",
    "target ranking",
    "discrimination",
    "discriminator",
    "model-label",
    "model_label",
    "model label",
    "provider-label",
    "provider_label",
    "provider label",
)

VISIBLE_LEAK_PATTERNS = (
    r"\bReview note\b",
    r"\bConclusion\b",
    r"\bClassification\b",
    r"\bSeverity\b",
    r"\bAction(?:s)?\b",
    r"\bRemediation\b",
    r"\bDECOY\b",
    r"\bNon-Supporting Source Cards\b",
    r"\bExplicit Non-Findings\b",
    r"\bthis is (?:a|an) .{0,60} defect at\b",
    r"\bthis is (?:a|an) .{0,60} risk at\b",
    r"\bblock merge\b",
    r"\bfix before merge\b",
    r"\boptimi[sz]e before merge\b",
    r"\bmeasure before merge\b",
    r"\badd (?:a )?regression test\b",
)

ADAPTER_SCORING_TOKENS = (
    "score_candidate",
    "validate_rubric",
    "jsonschema",
    "rubric.json",
    "components",
    "atoms",
    "findings_f1",
    "source_binding_f1",
    "case_fraction",
)


def _json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _scenario(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError(f"{path} must contain a YAML mapping")
    return loaded


def _atom_count(rubric: dict[str, Any]) -> int:
    return sum(len(component["atoms"]) for component in rubric["components"])


def _semantic_weight(rubric: dict[str, Any]) -> Decimal:
    return sum(
        (Decimal(str(component["weight"])) for component in rubric["components"] if component.get("semantic") is True),
        Decimal(0),
    )


def _max_declared_atom_points(rubric: dict[str, Any]) -> Decimal:
    max_points = Decimal(0)
    for component in rubric["components"]:
        component_weight = Decimal(str(component["weight"]))
        total_atom_weight = sum((Decimal(str(atom["weight"])) for atom in component["atoms"]), Decimal(0))
        for atom in component["atoms"]:
            atom_points = component_weight * Decimal(str(atom["weight"])) / total_atom_weight
            max_points = max(max_points, atom_points)
    return max_points


def _components_by_id(rubric: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {component["id"]: component for component in rubric["components"]}


def _all_atoms(rubric: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [
        (component["id"], atom)
        for component in rubric["components"]
        for atom in component["atoms"]
    ]


def _finding_targets(rubric: dict[str, Any]) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    for _, atom in _all_atoms(rubric):
        if atom.get("type") == "findings_f1":
            targets.extend(atom.get("expected", []))
    return targets


def _finding_targets_by_id(rubric: dict[str, Any]) -> dict[str, dict[str, Any]]:
    targets: dict[str, dict[str, Any]] = {}
    for component_id, atom in _all_atoms(rubric):
        if atom.get("type") != "findings_f1":
            continue
        for target in atom.get("expected", []):
            target_id = target.get(atom.get("reported_id_field", "id"))
            if not target_id:
                raise AssertionError(f"{component_id}.{atom['id']} finding target missing reported id")
            targets[str(target_id)] = {**target, "class": target.get("class", component_id)}
    return targets


def _source_binding_targets(rubric: dict[str, Any]) -> dict[str, set[str]]:
    targets: dict[str, set[str]] = {}
    for _, atom in _all_atoms(rubric):
        if atom.get("type") != "source_binding_f1":
            continue
        id_field = atom.get("id_field", "id")
        source_field = atom.get("source_ids_field", "source_ids")
        for expected in atom.get("expected", []):
            targets.setdefault(str(expected[id_field]), set()).update(expected.get(source_field, []))
    return targets


def _expected_source_bindings(expected: dict[str, Any]) -> dict[str, set[str]]:
    return {
        spec["source_ids"][0]: set(spec["source_ids"])
        for spec in expected["expected_findings"].values()
    }


def _expected_findings_by_anchor(expected: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        spec["source_ids"][0]: spec
        for spec in expected["expected_findings"].values()
    }


def _safe_target_sets(rubric: dict[str, Any]) -> list[set[str]]:
    safe_candidate_paths = {"non_findings", "known_safe_sources", "known_safe_surfaces", "rejected_sources"}
    targets: list[set[str]] = []
    for _, atom in _all_atoms(rubric):
        if atom.get("type") == "set_f1" and atom.get("candidate_path") in safe_candidate_paths:
            targets.append({str(value) for value in atom.get("expected", [])})
    return targets


def _entry_map(index: dict[str, Any], *candidate_keys: str) -> dict[str, dict[str, Any]]:
    for key in candidate_keys:
        value = index.get(key)
        if isinstance(value, dict):
            return {
                str(entry_id): ({**entry, "id": str(entry_id)} if isinstance(entry, dict) else {"id": str(entry_id)})
                for entry_id, entry in value.items()
            }
        if isinstance(value, list):
            entries: dict[str, dict[str, Any]] = {}
            for item in value:
                if not isinstance(item, dict) or not item.get("id"):
                    raise AssertionError(f"ground-truth {key} entries must be objects with id")
                entries[str(item["id"])] = item
            return entries
    raise AssertionError(f"ground-truth index missing one of: {', '.join(candidate_keys)}")


def _all_source_ids(expected: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for group_name in ("expected_findings", "expected_safe"):
        for spec in expected[group_name].values():
            ids.update(spec["source_ids"])
    return ids


def _safe_source_ids(expected: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for spec in expected["expected_safe"].values():
        ids.update(spec["source_ids"])
    return ids


def _json_strings(value: Any) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, dict):
        found: set[str] = set()
        for key, nested in value.items():
            found.add(str(key))
            found.update(_json_strings(nested))
        return found
    if isinstance(value, list):
        found: set[str] = set()
        for nested in value:
            found.update(_json_strings(nested))
        return found
    return set()


def _reference_findings(reference: dict[str, Any]) -> dict[str, dict[str, Any]]:
    findings = reference.get("findings")
    entries: dict[str, dict[str, Any]] = {}
    if isinstance(findings, dict):
        iterable = (
            {**item, "class": item.get("class", finding_class)}
            for finding_class, items in findings.items()
            if isinstance(items, list)
            for item in items
            if isinstance(item, dict)
        )
    elif isinstance(findings, list):
        iterable = (item for item in findings if isinstance(item, dict))
    else:
        raise AssertionError("reference-answer findings must be a mapping or list")

    for item in iterable:
        item_id = item.get("anchor_source_id")
        if not item_id:
            raise AssertionError("reference-answer finding entry missing anchor_source_id")
        entries[str(item_id)] = item
    return entries


def _reference_source_bindings(reference: dict[str, Any]) -> dict[str, set[str]]:
    bindings = reference.get("evidence", {}).get("bindings", {})
    if isinstance(bindings, dict):
        return {
            str(binding_id): set(binding.get("source_ids", []))
            for binding_id, binding in bindings.items()
            if isinstance(binding, dict)
        }
    raise AssertionError("reference evidence.bindings must be a mapping or list")


def _category_findings(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    findings = candidate.get("findings")
    if not isinstance(findings, dict):
        raise AssertionError("candidate findings must be a category mapping")
    entries: list[dict[str, Any]] = []
    for category_entries in findings.values():
        if not isinstance(category_entries, list):
            raise AssertionError("candidate finding categories must contain arrays")
        for entry in category_entries:
            if not isinstance(entry, dict):
                raise AssertionError("candidate finding entries must be objects")
            entries.append(entry)
    return entries


class L09PilotContractTests(unittest.TestCase):
    def test_l09_pilot_roots_have_basic_bundle_shape(self) -> None:
        for root_name, expected in PILOT_ROOTS.items():
            with self.subTest(root=root_name):
                root = PACK_ROOT / "Fixtures" / root_name
                self.assertTrue(root.is_dir(), f"missing pilot root: {root.relative_to(PACK_ROOT)}")

                for relative in EXPECTED_BUNDLE_FILES:
                    self.assertTrue((root / relative).is_file(), f"missing {root_name}/{relative}")

                scenario = _scenario(root / "scenario.yaml")
                self.assertEqual(scenario.get("scenario_id"), root_name)
                self.assertEqual(scenario.get("lane"), "L09")
                self.assertEqual(scenario.get("form"), expected["form"])
                self.assertEqual(scenario.get("candidate_artifact"), "candidate/review.json")
                self.assertEqual(scenario.get("allowed_write_paths"), ["candidate/review.json"])

                schema = _json(root / "inputs" / "output-schema.json")
                jsonschema.Draft202012Validator.check_schema(schema)
                schema_strings = _json_strings(schema)
                self.assertIn("anchor_source_id", schema_strings)
                self.assertNotIn("witness_id", schema_strings)
                self.assertNotIn("severity", schema.get("properties", {}))
                self.assertNotIn("oneOf", schema_strings)
                self.assertEqual(
                    {value for value in schema_strings if re.fullmatch(expected["source_id_pattern"], value)},
                    _all_source_ids(expected),
                )

                source = (root / "verifiers" / "score.py").read_text(encoding="utf-8")
                self.assertRegex(source, r"(from\s+v4_rubric\.cli\s+import|import\s+v4_rubric\.cli)")
                self.assertRegex(source, r"\b(main|run_cli|score_root)\s*\(")
                lowered_source = source.lower()
                for token in ADAPTER_SCORING_TOKENS:
                    self.assertNotIn(token, lowered_source, f"adapter contains scorer-owned token {token!r}")

    def test_required_probe_set_is_exact(self) -> None:
        for root_name in PILOT_ROOTS:
            with self.subTest(root=root_name):
                probes_root = PACK_ROOT / "Fixtures" / root_name / "oracle" / "probes"
                actual = sorted(path.stem for path in probes_root.glob("*.json"))
                self.assertEqual(actual, sorted(EXPECTED_PROBES))

    def test_competent_derived_probe_uses_visible_anchor_shape(self) -> None:
        for root_name, expected in PILOT_ROOTS.items():
            root = PACK_ROOT / "Fixtures" / root_name
            root_prefix = "B" if expected["form"] == "base" else "F"
            source_pattern = re.compile(expected["source_id_pattern"])
            hidden_pattern = re.compile(rf"{root_prefix}\d{{2}}[-\w]*|{root_prefix}-(?!CARD-\d{{3}})[A-Z0-9][A-Z0-9-]*")
            source_ids = _all_source_ids(expected)
            finding_anchor_ids = {
                spec["source_ids"][0]
                for spec in expected["expected_findings"].values()
            }
            probe = _json(root / "oracle" / "probes" / f"{COMPETENT_DERIVED_PROBE}.json")

            with self.subTest(root=root_name):
                self.assertIsInstance(probe, dict)
                self.assertNotIn("severity", probe, f"{root_name} must score severity on finding rows only")
                self.assertNotIn("witness_id", _json_strings(probe), f"{root_name} must not invent witness ids")
                self.assertEqual(
                    {value for value in _json_strings(probe) if hidden_pattern.fullmatch(value)},
                    set(),
                    f"{root_name} must not use hidden oracle ids",
                )

                findings = _category_findings(probe)
                self.assertEqual({finding["anchor_source_id"] for finding in findings}, finding_anchor_ids)
                for finding in findings:
                    self.assertEqual(set(finding), {"anchor_source_id", "file", "symbol", "severity"})
                    self.assertRegex(finding["anchor_source_id"], source_pattern)

                bindings = probe.get("evidence", {}).get("bindings")
                self.assertIsInstance(bindings, dict)
                self.assertEqual(set(bindings), finding_anchor_ids)
                for anchor_id, binding in bindings.items():
                    self.assertRegex(anchor_id, source_pattern)
                    self.assertLessEqual(set(binding.get("source_ids", [])), source_ids)

                actions = probe.get("actions")
                self.assertIsInstance(actions, dict)
                self.assertEqual(set(actions), finding_anchor_ids)

    def test_visible_inputs_are_raw_evidence_and_neutral(self) -> None:
        for root_name, expected in PILOT_ROOTS.items():
            root = PACK_ROOT / "Fixtures" / root_name
            with self.subTest(root=root_name):
                visible_paths = [root / "inputs" / "task.md", root / "inputs" / "sources" / "source-cards.md"]
                visible_text = "\n".join(path.read_text(encoding="utf-8") for path in visible_paths)
                for pattern in VISIBLE_LEAK_PATTERNS:
                    self.assertIsNone(
                        re.search(pattern, visible_text, flags=re.IGNORECASE | re.DOTALL),
                        f"{root_name} visible inputs leak dictated review conclusion via {pattern!r}",
                    )
                root_prefix = "B" if expected["form"] == "base" else "F"
                non_neutral_ids = sorted(set(re.findall(
                    rf"\b{root_prefix}-(?!CARD-\d{{3}}\b)[A-Z0-9][A-Z0-9-]*\b|\b{root_prefix}\d{{2}}[-\w]*\b",
                    visible_text,
                )))
                self.assertEqual(non_neutral_ids, [], f"{root_name} visible inputs must expose only neutral CARD ids")
                for hidden_id in sorted(set(expected["expected_findings"]) | set(expected["expected_safe"])):
                    self.assertNotIn(hidden_id, visible_text, f"{root_name} leaks hidden oracle id {hidden_id}")

                task_text = (root / "inputs" / "task.md").read_text(encoding="utf-8")
                for finding_class in [spec["class"] for spec in expected["expected_findings"].values()]:
                    self.assertNotIn(
                        finding_class,
                        task_text,
                        f"{root_name}/inputs/task.md must not publish expected finding class {finding_class!r}",
                    )

                card_text = (root / "inputs" / "sources" / "source-cards.md").read_text(encoding="utf-8")
                neutral_ids = set(re.findall(expected["source_id_pattern"], card_text))
                self.assertEqual(neutral_ids, _all_source_ids(expected))

    def test_ground_truth_inventory_matches_design(self) -> None:
        for root_name, expected in PILOT_ROOTS.items():
            root = PACK_ROOT / "Fixtures" / root_name
            ground_truth_root = root / "oracle" / "ground-truth"
            index_path = ground_truth_root / "index.json"
            with self.subTest(root=root_name):
                self.assertTrue(index_path.is_file(), f"missing {root_name}/oracle/ground-truth/index.json")
                index = _json(index_path)
                self.assertIsInstance(index, dict)
                self.assertEqual(index.get("scenario_id"), root_name)

                finding_entries = _entry_map(index, "real_findings", "findings")
                safe_entries = _entry_map(index, "safe_sources", "known_safe_sources", "non_findings")
                self.assertEqual(set(finding_entries), set(expected["expected_findings"]))
                self.assertEqual(set(safe_entries), set(expected["expected_safe"]))

                for finding_id, spec in expected["expected_findings"].items():
                    entry = finding_entries[finding_id]
                    self.assertEqual(entry.get("file"), spec["file"])
                    self.assertEqual(entry.get("symbol"), spec["symbol"])
                    self.assertEqual(entry.get("class"), spec["class"])
                    self.assertEqual(set(entry.get("source_ids", [])), set(spec["source_ids"]))
                    self.assertEqual(set(entry.get("proof_files", [])), set(spec["proof_files"]))
                    if "depends_on" in spec:
                        self.assertEqual(entry.get("depends_on"), spec["depends_on"])
                    if "cross_diff_source_ids" in spec:
                        self.assertEqual(set(entry.get("cross_diff_source_ids", [])), set(spec["cross_diff_source_ids"]))
                    for relative in spec["proof_files"]:
                        self.assertTrue((ground_truth_root / relative).is_file(), f"missing proof file {relative}")

                for safe_id, spec in expected["expected_safe"].items():
                    entry = safe_entries[safe_id]
                    self.assertEqual(set(entry.get("source_ids", [])), set(spec["source_ids"]))
                    self.assertEqual(set(entry.get("proof_files", [])), set(spec["proof_files"]))
                    for relative in spec["proof_files"]:
                        self.assertTrue((ground_truth_root / relative).is_file(), f"missing proof file {relative}")

                if "numeric_target" in expected:
                    targets = _entry_map(index, "numeric_targets")
                    numeric = expected["numeric_target"]
                    entry = targets[numeric["id"]]
                    self.assertEqual(entry.get("candidate_path"), numeric["candidate_path"])
                    self.assertEqual(entry.get("expected"), numeric["expected"])
                    self.assertEqual(entry.get("unit"), numeric["unit"])
                    self.assertEqual(entry.get("full_tolerance"), numeric["full_tolerance"])
                    self.assertEqual(entry.get("zero_tolerance"), numeric["zero_tolerance"])
                    self.assertEqual(set(entry.get("proof_files", [])), set(numeric["proof_files"]))

    def test_rubric_shape_counts_and_commitment_policy(self) -> None:
        for root_name, expected in PILOT_ROOTS.items():
            with self.subTest(root=root_name):
                root = PACK_ROOT / "Fixtures" / root_name
                rubric = _json(root / "oracle" / "rubric.json")
                self.assertIsInstance(rubric, dict)
                self.assertEqual(rubric.get("scenario_id"), root_name)
                validate_rubric(rubric)

                component_profile = {component["id"]: component["weight"] for component in rubric["components"]}
                self.assertEqual(component_profile, expected["component_profile"])
                self.assertEqual(sum(component_profile.values()), 100)
                self.assertGreaterEqual(_semantic_weight(rubric), Decimal(70))
                self.assertLessEqual(_max_declared_atom_points(rubric), Decimal(10))
                self.assertGreaterEqual(_atom_count(rubric), 12)

                finding_targets = _finding_targets_by_id(rubric)
                expected_by_anchor = _expected_findings_by_anchor(expected)
                self.assertEqual(set(finding_targets), set(expected_by_anchor))
                self.assertEqual(len(_finding_targets(rubric)), 4)
                rubric_strings = _json_strings(rubric)
                for hidden_id in expected["expected_findings"]:
                    self.assertNotIn(hidden_id, rubric_strings, f"{root_name} rubric uses hidden id {hidden_id}")
                for anchor_id, spec in expected_by_anchor.items():
                    target = finding_targets[anchor_id]
                    self.assertEqual(target.get("anchor_source_id"), anchor_id)
                    self.assertEqual(target.get("file"), spec["file"])
                    self.assertEqual(target.get("symbol"), spec["symbol"])
                    self.assertEqual(target.get("class"), spec["class"])
                self.assertEqual(_source_binding_targets(rubric), _expected_source_bindings(expected))

                expected_safe_ids = set(expected["expected_safe"])
                safe_sources = _safe_source_ids(expected)
                self.assertIn(
                    True,
                    [target_set == expected_safe_ids or target_set == safe_sources for target_set in _safe_target_sets(rubric)],
                    f"{root_name} rubric must target exactly the two designed safe-source groups",
                )

                committed_atoms = [
                    (component_id, atom)
                    for component_id, atom in _all_atoms(rubric)
                    if atom.get("commitment") is True
                ]
                self.assertEqual(
                    [(component_id, atom["id"]) for component_id, atom in committed_atoms],
                    [("merge_clearance" if expected["form"] == "base" else "scope_gate", "merge-clearance")],
                )
                committed_atom = committed_atoms[0][1]
                self.assertEqual(committed_atom.get("type"), "categorical")
                self.assertEqual(committed_atom.get("candidate_path"), "review_gate.merge_clearance")
                self.assertEqual(str(committed_atom.get("expected")).lower(), "needs-review")

                for component_id, atom in _all_atoms(rubric):
                    if (component_id, atom["id"]) == (committed_atoms[0][0], committed_atom["id"]):
                        continue
                    self.assertFalse(
                        atom.get("commitment") is True,
                        f"{root_name} {component_id}.{atom['id']} must not be a cap-bearing judgment atom",
                    )

                if expected["form"] == "frontier":
                    numeric_atoms = [
                        atom
                        for component_id, atom in _all_atoms(rubric)
                        if component_id == "numeric" and atom.get("type") == "numeric"
                    ]
                    self.assertEqual(len(numeric_atoms), 1)
                    numeric = numeric_atoms[0]
                    target = expected["numeric_target"]
                    self.assertEqual(numeric.get("candidate_path"), target["candidate_path"])
                    self.assertEqual(numeric.get("expected"), target["expected"])
                    self.assertEqual(numeric.get("unit"), target["unit"])
                    self.assertEqual(numeric.get("full_tolerance"), target["full_tolerance"])
                    self.assertEqual(numeric.get("zero_tolerance"), target["zero_tolerance"])
                    self.assertFalse(numeric.get("commitment", False))

    def test_reference_and_probes_cross_check_index_and_metadata(self) -> None:
        for root_name, expected in PILOT_ROOTS.items():
            root = PACK_ROOT / "Fixtures" / root_name
            with self.subTest(root=root_name):
                files_to_scan = [
                    path
                    for path in root.rglob("*")
                    if path.is_file() and path.suffix.lower() in {".json", ".md", ".yaml", ".yml"}
                ]
                for path in files_to_scan:
                    lowered = path.read_text(encoding="utf-8").lower()
                    for token in FORBIDDEN_METADATA_TOKENS:
                        self.assertNotIn(
                            token,
                            lowered,
                            f"{path.relative_to(PACK_ROOT)} contains forbidden metadata token {token!r}",
                        )

                reference = _json(root / "oracle" / "reference-answer.json")
                self.assertIsInstance(reference, dict)
                self.assertNotIn("severity", reference)
                self.assertNotIn("witness_id", _json_strings(reference))
                reference_findings = _reference_findings(reference)
                expected_by_anchor = _expected_findings_by_anchor(expected)
                self.assertEqual(set(reference_findings), set(expected_by_anchor))
                self.assertEqual(len(reference_findings), 4)
                for anchor_id, spec in expected_by_anchor.items():
                    reference_finding = reference_findings[anchor_id]
                    self.assertEqual(reference_finding.get("anchor_source_id"), anchor_id)
                    self.assertEqual(reference_finding.get("file"), spec["file"])
                    self.assertEqual(reference_finding.get("symbol"), spec["symbol"])
                    self.assertEqual(reference_finding.get("class"), spec["class"])
                self.assertEqual(_reference_source_bindings(reference), _expected_source_bindings(expected))

                reference_strings = _json_strings(reference)
                source_ids = _all_source_ids(expected)
                source_pattern = re.compile(expected["source_id_pattern"])
                self.assertEqual({value for value in reference_strings if source_pattern.fullmatch(value)}, source_ids)
                expected_safe_ids = set(expected["expected_safe"])
                safe_sources = _safe_source_ids(expected)
                self.assertTrue(
                    expected_safe_ids <= reference_strings or safe_sources <= reference_strings,
                    f"{root_name} reference must encode the two designed safe sources",
                )

                root_prefix = "B" if expected["form"] == "base" else "F"
                for probe_name in EXPECTED_PROBES:
                    probe_path = root / "oracle" / "probes" / f"{probe_name}.json"
                    self.assertTrue(probe_path.is_file(), f"missing {root_name}/oracle/probes/{probe_name}.json")
                    probe = _json(probe_path)
                    self.assertIsInstance(probe, dict)
                    self.assertNotIn("severity", probe, f"{root_name}/{probe_name} must score severity on finding rows")
                    self.assertNotIn("witness_id", _json_strings(probe), f"{root_name}/{probe_name} must not use witness ids")
                    mentioned_sources = {
                        value for value in _json_strings(probe) if source_pattern.fullmatch(value)
                    }
                    self.assertLessEqual(mentioned_sources, source_ids)
                    scenario_like_ids = {
                        value
                        for value in _json_strings(probe)
                        if re.fullmatch(rf"{root_prefix}\d{{2}}[-\w]*|{root_prefix}-CARD-\d{{3}}", value)
                    }
                    self.assertLessEqual(scenario_like_ids, source_ids)
                    old_oracle_ids = {
                        value
                        for value in _json_strings(probe)
                        if re.fullmatch(rf"{root_prefix}-(?!CARD-\d{{3}})[A-Z0-9][A-Z0-9-]*", value)
                    }
                    self.assertEqual(old_oracle_ids, set(), f"{root_name}/{probe_name} uses non-design oracle ids")

                if expected["form"] == "frontier":
                    measurement = reference.get("profile_measurements", {}).get("permission_lookup_calls")
                    self.assertEqual(measurement, {"value": 1201, "unit": "calls"})


if __name__ == "__main__":
    unittest.main()
