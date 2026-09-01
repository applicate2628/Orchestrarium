#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Check the N25 UI dirty-state gauntlet.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--expect-start-state", action="store_true")
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def strip_quotes(value: str):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_simple_yaml(path: Path):
    data = {}
    current_key = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - "):
            data.setdefault(current_key, []).append(strip_quotes(line[4:].strip()))
            continue
        if ":" not in line or line.startswith(" "):
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        if value == "":
            data[key] = []
            current_key = key
        elif value == "[]":
            data[key] = []
            current_key = None
        else:
            data[key] = strip_quotes(value)
            current_key = None
    return data


def top_level_yaml_keys(path: Path):
    keys = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if line and not line.startswith(" ") and not line.startswith("#") and ":" in line:
            keys.append(line.split(":", 1)[0].strip())
    return keys


def require(condition: bool, message: str, errors: list[str]):
    if not condition:
        errors.append(message)


def check_shape(root: Path, contract: dict, errors: list[str]):
    actual_entries = sorted(path.name for path in root.iterdir())
    require(
        actual_entries == sorted(contract["required_top_level_entries"]),
        f"Top-level bundle entries drifted: {actual_entries}",
        errors,
    )
    scenario = root / "scenario.yaml"
    require(top_level_yaml_keys(scenario) == contract["scenario_yaml_fields"], "scenario.yaml field order drifted", errors)
    require(parse_simple_yaml(scenario) == contract["expected_metadata"], "scenario.yaml metadata mismatch", errors)
    for path in contract["required_bundle_paths"]:
        require((root / path).exists(), f"Missing required bundle path: {path}", errors)


def run_node_probe(root: Path):
    state_uri = (root / "candidate" / "workspace" / "src" / "editor-state.mjs").as_uri()
    render_uri = (root / "candidate" / "workspace" / "src" / "editor-panel.mjs").as_uri()
    probe = f"""
import {{ renderEditor }} from {json.dumps(render_uri)};
import {{
  activeItem,
  attemptNavigate,
  createEditorState,
  discardActive,
  isDirty,
  saveActive,
  updateField,
}} from {json.dumps(state_uri)};

const items = [
  {{ id: "profile", label: "Profile Settings", fields: {{ title: "Profile", slug: "profile", summary: "Profile summary" }} }},
  {{ id: "billing", label: "Billing Plan", fields: {{ title: "Billing", slug: "billing", summary: "Billing summary" }} }},
];

const failures = [];
function assertEqual(actual, expected, label) {{
  if (actual !== expected) throw new Error(`${{label}}: expected ${{expected}}, got ${{actual}}`);
}}
function assertTruthy(value, label) {{
  if (!value) throw new Error(`${{label}} missing`);
}}
function assertMatch(value, pattern, label) {{
  if (!pattern.test(value)) throw new Error(`${{label}} missing`);
}}
function record(id, fn) {{
  try {{ fn(); }} catch (error) {{ failures.push({{ id, detail: String(error.message || error) }}); }}
}}

record("dirty-preserves-by-item", () => {{
  let state = createEditorState(items);
  state = updateField(state, "title", "Profile draft");
  assertEqual(isDirty(state, "profile"), true, "profile dirty before navigation");
  state = attemptNavigate(state, "billing");
  assertEqual(isDirty(state, "profile"), true, "profile dirty after blocked navigation");
  assertEqual(activeItem(state).draft.title, "Profile draft", "draft preserved");
}});

record("navigation-guard", () => {{
  let state = createEditorState(items);
  state = updateField(state, "summary", "Unsaved summary");
  state = attemptNavigate(state, "billing");
  assertEqual(state.activeId, "profile", "active route blocked");
  assertEqual(state.blockedNavigation?.targetId, "billing", "blocked target recorded");
  assertMatch(state.status.text, /unsaved/i, "blocked navigation status");
}});

record("validation-blocks-save", () => {{
  let state = createEditorState(items);
  state = updateField(state, "slug", "Bad Slug!");
  state = saveActive(state, {{ ok: true }});
  assertEqual(isDirty(state, "profile"), true, "invalid draft remains dirty");
  assertTruthy(activeItem(state).errors.slug, "slug error");
  assertEqual(activeItem(state).baseline.slug, "profile", "baseline not committed");
}});

record("failed-save-keeps-dirty", () => {{
  let state = createEditorState(items);
  state = updateField(state, "summary", "Server-side update");
  state = saveActive(state, {{ ok: false, message: "API rejected" }});
  assertEqual(isDirty(state, "profile"), true, "failed save dirty");
  assertEqual(activeItem(state).baseline.summary, "Profile summary", "failed save baseline");
  assertEqual(state.status.type, "error", "failed save status");
  assertMatch(state.status.text, /API rejected/, "failed save message");
}});

record("discard-current-baseline", () => {{
  let state = createEditorState(items);
  state = attemptNavigate(state, "billing");
  state = updateField(state, "title", "Billing draft");
  state = discardActive(state);
  assertEqual(activeItem(state).draft.title, "Billing", "billing baseline restored");
  assertEqual(isDirty(state, "billing"), false, "billing clean after discard");
}});

record("focus-return", () => {{
  let state = createEditorState(items);
  state = updateField(state, "title", "");
  state = saveActive(state, {{ ok: true }});
  assertEqual(state.focusId, "field-title-profile", "invalid focus");
  state = updateField(state, "title", "Profile edited");
  state = saveActive(state, {{ ok: true }});
  assertEqual(state.focusId, "status-profile", "success focus");
  state = updateField(state, "summary", "temporary");
  state = discardActive(state);
  assertEqual(state.focusId, "field-title-profile", "discard focus");
}});

record("render-accessibility-state", () => {{
  let state = createEditorState(items);
  state = updateField(state, "slug", "Bad Slug!");
  state = saveActive(state, {{ ok: true }});
  const invalidHtml = renderEditor(state);
  assertMatch(invalidHtml, /id="status-profile"/, "stable status id");
  assertMatch(invalidHtml, /aria-live="polite"/, "live status");
  assertMatch(invalidHtml, /aria-invalid="true"/, "invalid field");
  assertMatch(invalidHtml, /aria-describedby="error-slug-profile"/, "described invalid field");
  assertMatch(invalidHtml, /id="error-slug-profile"/, "visible error id");
  state = updateField(state, "slug", "profile-draft");
  const dirtyHtml = renderEditor(state);
  assertMatch(dirtyHtml, /data-dirty="true"/, "dirty marker");
  assertMatch(dirtyHtml, /data-blocked-target=""/, "empty blocked target marker");
  assertMatch(renderEditor(createEditorState(items)), /<button[^>]+data-action="save"[^>]+disabled/, "clean save disabled");
}});

console.log(JSON.stringify(failures));
"""
    with tempfile.TemporaryDirectory() as tmp:
        probe_path = Path(tmp) / "probe.mjs"
        probe_path.write_text(probe, encoding="utf-8")
        result = subprocess.run(["node", str(probe_path)], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return [{"id": "node-probe-runtime", "detail": (result.stderr or result.stdout).strip()}]
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return [{"id": "node-probe-json", "detail": str(exc)}]


def check_css(root: Path, contract: dict):
    css = (root / "candidate" / "workspace" / "src" / "editor.css").read_text(encoding="utf-8")
    missing = [marker for marker in contract["required_css_markers"] if marker not in css]
    if missing:
        return [{"id": "css-stability", "detail": ", ".join(missing)}]
    return []


def run_direct_tests(root: Path, errors: list[str]):
    workspace = root / "candidate" / "workspace"
    result = subprocess.run(["node", "tests/editor-contract.test.mjs"], cwd=workspace, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part).strip()
        errors.append(f"Direct tests failed: {output or 'no output'}")


def check_no_hardcoding(root: Path, contract: dict, errors: list[str]):
    terms = [term.lower() for term in contract["prohibited_candidate_terms"]]
    for rel_path in contract["expected_metadata"]["allowed_change_surface"]:
        text = (root / rel_path).read_text(encoding="utf-8", errors="replace").lower()
        for term in terms:
            if term in text:
                errors.append(f"Candidate file {rel_path} contains prohibited literal: {term}")


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    errors: list[str] = []

    if not root.exists():
        print(f"Bundle root does not exist: {root}", file=sys.stderr)
        return 1

    contract = load_json(root / "oracle" / "ui-dirty-contract.json")
    check_shape(root, contract, errors)

    if not args.bundle_shape_only:
        failures = run_node_probe(root) + check_css(root, contract)
        failure_ids = sorted(failure["id"] for failure in failures)
        if args.expect_start_state:
            expected = sorted(contract["expected_start_state_failures"])
            require(failure_ids == expected, f"Expected start-state failures {expected}, found {failure_ids}", errors)
        else:
            run_direct_tests(root, errors)
            check_no_hardcoding(root, contract, errors)
            if failures:
                rendered = json.dumps(failures, indent=2, sort_keys=True)
                errors.append(f"Completed candidate still fails UI dirty-state invariants: {rendered}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if args.bundle_shape_only:
        mode = "bundle shape"
    elif args.expect_start_state:
        mode = "start state"
    else:
        mode = "completed run"
    print(f"N25 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
