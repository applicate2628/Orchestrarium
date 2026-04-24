#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


BACKGROUND = [17, 19, 24]
FOCUS = [250, 204, 21]
ALERT = [249, 115, 22]
SELECTED_CENTER = [250, 62, 38]
LEGEND = {
    -1: [147, 197, 253],
    0: [248, 250, 252],
    1: [252, 165, 165],
    2: [220, 38, 38],
}


def parse_args():
    parser = argparse.ArgumentParser(description="Check the N60 UI/visual/state reentry bundle.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--expect-start-state", action="store_true")
    parser.add_argument("--metrics-out", type=Path)
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def strip_quotes(value: str) -> str:
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
    state_uri = (root / "candidate" / "workspace" / "src" / "console-state.mjs").as_uri()
    view_uri = (root / "candidate" / "workspace" / "src" / "console-view.mjs").as_uri()
    layout_uri = (root / "candidate" / "workspace" / "src" / "console-layout.mjs").as_uri()
    raster_uri = (root / "candidate" / "workspace" / "src" / "console-raster.mjs").as_uri()
    probe = f"""
import {{
  activeRecord,
  applyCommandFilter,
  attemptRecordNavigation,
  createConsoleState,
  discardActiveRecord,
  isDirty,
  moveCommandFocus,
  saveActiveRecord,
  selectActiveCommand,
  updateDraftField
}} from {json.dumps(state_uri)};
import {{ renderConsole }} from {json.dumps(view_uri)};
import {{ computeLayout }} from {json.dumps(layout_uri)};
import {{ exportPpm, renderRaster }} from {json.dumps(raster_uri)};

const records = [
  {{
    id: "api-17",
    label: "API Incident",
    owner: "incident",
    baseline: {{ title: "API incident", slug: "api-incident", severity: "high", summary: "Queue API retry storm" }}
  }},
  {{
    id: "billing-29",
    label: "Billing Review",
    owner: "finance",
    baseline: {{ title: "Billing review", slug: "billing-review", severity: "medium", summary: "Invoice queue drift" }}
  }},
  {{
    id: "release-03",
    label: "Release Approval With Long Localized Label That Must Wrap Cleanly",
    owner: "release",
    baseline: {{ title: "Release approval", slug: "release-approval", severity: "low", summary: "Long localized label probe" }}
  }}
];

const commands = [
  {{ id: "approve", group: "triage", label: "Approve rollback", owner: "incident", returnCue: "Return to incident queue" }},
  {{ id: "approve", group: "security", label: "Approve firewall exception", owner: "security", returnCue: "Return to security queue", disabled: true }},
  {{ id: "inspect", group: "ops", label: "Inspect deployment health", owner: "ops", returnCue: "Return to deployment health" }},
  {{ id: "publish", group: "release", label: "Publish production deploy", owner: "release", returnCue: "Return to release train", disabled: true }},
  {{ id: "rollback", group: "ops", label: "Rollback failed deployment", owner: "ops", returnCue: "Return to incident timeline" }}
];

const failures = [];
function assertEqual(actual, expected, label) {{
  if (actual !== expected) throw new Error(`${{label}}: expected ${{expected}}, got ${{actual}}`);
}}
function assertTruthy(value, label) {{
  if (!value) throw new Error(`${{label}} missing`);
}}
function assertMatch(value, pattern, label) {{
  if (!pattern.test(String(value))) throw new Error(`${{label}} missing`);
}}
function assertPixel(frame, x, y, expected, label) {{
  const actual = frame?.[y]?.[x];
  if (!Array.isArray(actual) || actual.length !== 3 || actual.some((value, index) => value !== expected[index])) {{
    throw new Error(`${{label}}: expected ${{expected.join(",")}}, got ${{actual}}`);
  }}
}}
function record(id, fn) {{
  try {{ fn(); }} catch (error) {{ failures.push({{ id, detail: String(error.message || error) }}); }}
}}
function boxById(layout, id) {{
  return (layout.boxes || []).find((box) => box.id === id);
}}
function overlaps(a, b) {{
  return a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y;
}}
function inside(box, viewport) {{
  return box.x >= 0 && box.y >= 0 && box.width > 0 && box.height > 0 &&
    box.x + box.width <= viewport.width && box.y + box.height <= viewport.height;
}}

record("command-focus-skip", () => {{
  let state = createConsoleState(records, commands);
  assertEqual(state.activeCommandKey, "triage:approve", "initial active command");
  state = moveCommandFocus(state, "down");
  assertEqual(state.activeCommandKey, "ops:inspect", "skip disabled duplicate approve");
  state = moveCommandFocus(state, "down");
  assertEqual(state.activeCommandKey, "ops:rollback", "skip disabled publish");
  state = moveCommandFocus(state, "down");
  assertEqual(state.activeCommandKey, "triage:approve", "wrap enabled commands");
}});

record("command-filter-owner", () => {{
  let state = {{ ...createConsoleState(records, commands), activeCommandKey: "ops:rollback", lastStableCommandKey: "ops:rollback" }};
  state = applyCommandFilter(state, "approve");
  assertEqual(state.activeCommandKey, "triage:approve", "filter picks enabled owner-qualified approve");
  const selected = selectActiveCommand(state);
  assertEqual(selected.selected.owner, "incident", "selected owner");
  assertEqual(selected.selected.returnCue, "Return to incident queue", "selected return cue");
  state = {{ ...createConsoleState(records, commands), commandFilter: "approve", activeCommandKey: "security:approve" }};
  assertEqual(selectActiveCommand(state).selected, null, "disabled duplicate cannot be selected");
}});

record("dirty-state-per-record", () => {{
  let state = createConsoleState(records, commands);
  state = updateDraftField(state, "title", "API draft");
  assertEqual(isDirty(state, "api-17"), true, "api dirty before navigation");
  state = attemptRecordNavigation(state, "billing-29");
  assertEqual(state.activeRecordId, "api-17", "dirty navigation blocked");
  assertEqual(isDirty(state, "api-17"), true, "api dirty after blocked navigation");
  assertEqual(activeRecord(state).draft.title, "API draft", "draft preserved");
  assertEqual(isDirty(state, "billing-29"), false, "other record clean");
}});

record("navigation-guard-target", () => {{
  let state = createConsoleState(records, commands);
  state = updateDraftField(state, "summary", "Unsaved API summary");
  state = attemptRecordNavigation(state, "billing-29");
  assertEqual(state.blockedNavigation?.targetId, "billing-29", "blocked target");
  assertMatch(state.blockedNavigation?.visibleReturnCue, /Resolve unsaved review edits before changing record/, "visible blocked cue");
  assertMatch(state.status?.text, /Resolve unsaved review edits before changing record/, "status blocked cue");
  state = discardActiveRecord(state);
  state = attemptRecordNavigation(state, "billing-29");
  assertEqual(state.activeRecordId, "billing-29", "navigation after discard");
  assertEqual(isDirty(state, "api-17"), false, "discard cleaned active record baseline");
}});

record("validation-and-save", () => {{
  let state = createConsoleState(records, commands);
  state = updateDraftField(state, "slug", "Bad Slug!");
  state = saveActiveRecord(state, {{ ok: true }});
  assertEqual(isDirty(state, "api-17"), true, "invalid save remains dirty");
  assertTruthy(activeRecord(state).errors.slug, "slug error");
  assertEqual(activeRecord(state).baseline.slug, "api-incident", "invalid baseline unchanged");
  state = updateDraftField(state, "slug", "api-incident-v2");
  state = updateDraftField(state, "summary", "Server side update");
  state = saveActiveRecord(state, {{ ok: false, message: "Write API timeout" }});
  assertEqual(isDirty(state, "api-17"), true, "failed save remains dirty");
  assertEqual(activeRecord(state).baseline.summary, "Queue API retry storm", "failed save baseline unchanged");
  assertEqual(state.status.type, "error", "failed save status");
  assertMatch(state.status.text, /Write API timeout/, "failed save message");
  state = saveActiveRecord(state, {{ ok: true }});
  assertEqual(isDirty(state, "api-17"), false, "successful save clears active dirty");
  assertEqual(activeRecord(state).baseline.slug, "api-incident-v2", "successful save baseline");
}});

record("focus-return", () => {{
  let state = createConsoleState(records, commands);
  state = updateDraftField(state, "slug", "Bad Slug!");
  state = saveActiveRecord(state, {{ ok: true }});
  assertEqual(state.focusId, "field-slug-api-17", "validation focus");
  state = updateDraftField(state, "slug", "api-incident-v2");
  state = saveActiveRecord(state, {{ ok: true }});
  assertEqual(state.focusId, "status-api-17", "save success focus");
  state = updateDraftField(state, "title", "Temporary title");
  state = discardActiveRecord(state);
  assertEqual(state.focusId, "field-title-api-17", "discard focus");
}});

record("render-accessibility", () => {{
  let state = createConsoleState(records, commands);
  state = updateDraftField(state, "title", "API draft");
  state = attemptRecordNavigation(state, "billing-29");
  state = updateDraftField(state, "slug", "Bad Slug!");
  state = saveActiveRecord(state, {{ ok: true }});
  const html = renderConsole(state);
  assertMatch(html, /role="listbox"/, "listbox role");
  assertMatch(html, /aria-activedescendant="command-option-triage-approve"/, "active descendant");
  assertMatch(html, /id="command-option-triage-approve"/, "stable active option id");
  assertMatch(html, /role="option"/, "option role");
  assertMatch(html, /aria-selected="true"/, "selected option");
  assertMatch(html, /data-owner="incident"/, "owner marker");
  assertMatch(html, /data-visible-return-cue="Return to incident queue"/, "return cue data");
  assertMatch(html, />Return to incident queue</, "visible return cue");
  assertMatch(html, /role="tablist"/, "tablist role");
  assertMatch(html, /data-dirty="true"/, "dirty marker");
  assertMatch(html, /data-blocked-target="billing-29"/, "blocked target marker");
  assertMatch(html, /Resolve unsaved review edits before changing record/, "blocked cue text");
  assertMatch(html, /id="status-api-17"/, "stable status id");
  assertMatch(html, /aria-live="polite"/, "live status");
  assertMatch(html, /aria-invalid="true"/, "invalid field");
  assertMatch(html, /aria-describedby="error-slug-api-17"/, "invalid description");
  assertMatch(html, /id="error-slug-api-17"/, "visible error id");
  assertMatch(renderConsole(createConsoleState(records, commands)), /<button[^>]+data-action="save"[^>]+disabled/, "clean save disabled");
}});

record("layout-responsive-containment", () => {{
  const state = createConsoleState(records, commands);
  for (const viewport of [{{ width: 320, height: 720 }}, {{ width: 768, height: 720 }}, {{ width: 1280, height: 720 }}]) {{
    const layout = computeLayout(viewport, state);
    for (const id of ["command-palette", "record-tabs", "detail-form", "raster-preview", "save-button", "discard-button"]) {{
      assertTruthy(boxById(layout, id), `layout box ${{id}}`);
    }}
    for (const box of layout.boxes) {{
      if (!inside(box, viewport)) throw new Error(`box ${{box.id}} outside viewport ${{viewport.width}}`);
    }}
    const detail = boxById(layout, "detail-form");
    const raster = boxById(layout, "raster-preview");
    if (viewport.width <= 480 && raster.y < detail.y + detail.height) {{
      throw new Error("compact raster preview must stack below detail form");
    }}
    if (viewport.width >= 1024 && raster.x < detail.x + detail.width + 16) {{
      throw new Error("desktop raster preview must sit to the right of detail form");
    }}
  }}
}});

record("layout-target-overlap", () => {{
  const layout = computeLayout({{ width: 320, height: 720 }}, createConsoleState(records, commands));
  const interactive = layout.boxes.filter((box) => ["command", "tab", "button"].includes(box.role));
  for (const box of interactive) {{
    if (box.width < 32 || box.height < 32) throw new Error(`interactive target too small: ${{box.id}}`);
  }}
  for (let left = 0; left < interactive.length; left += 1) {{
    for (let right = left + 1; right < interactive.length; right += 1) {{
      if (overlaps(interactive[left], interactive[right])) {{
        throw new Error(`interactive overlap: ${{interactive[left].id}} / ${{interactive[right].id}}`);
      }}
    }}
  }}
}});

record("raster-transparent-gap", () => {{
  const frame = renderRaster({{
    width: 28,
    height: 18,
    background: "#111318",
    grid: {{ x: 2, y: 3, cell: 4, gap: 2 }},
    values: [[-1, 0, null, 2], [0, 1, 2, -1], [null, 1, 0, 2]],
    selected: {{ row: 1, col: 2 }},
    alert: {{ row: 1, col: 2 }},
    legend: {{ x: 24, y: 2, width: 2, values: [-1, 0, 1, 2] }}
  }});
  assertEqual(frame.length, 18, "raster height");
  assertEqual(frame[0].length, 28, "raster width");
  assertPixel(frame, 15, 4, [17, 19, 24], "null cell gap");
}});

record("raster-selected-alert-layer", () => {{
  const frame = renderRaster({{
    width: 28,
    height: 18,
    background: "#111318",
    grid: {{ x: 2, y: 3, cell: 4, gap: 2 }},
    values: [[-1, 0, null, 2], [0, 1, 2, -1], [null, 1, 0, 2]],
    selected: {{ row: 1, col: 2 }},
    alert: {{ row: 1, col: 2 }},
    legend: {{ x: 24, y: 2, width: 2, values: [-1, 0, 1, 2] }}
  }});
  assertPixel(frame, 14, 9, [250, 204, 21], "selected focus ring");
  assertPixel(frame, 15, 10, [249, 115, 22], "alert stripe");
  assertPixel(frame, 16, 11, [250, 62, 38], "selected center highlight");
}});

record("raster-legend-order", () => {{
  const frame = renderRaster({{
    width: 28,
    height: 18,
    background: "#111318",
    grid: {{ x: 2, y: 3, cell: 4, gap: 2 }},
    values: [[-1, 0, null, 2], [0, 1, 2, -1], [null, 1, 0, 2]],
    selected: {{ row: 1, col: 2 }},
    alert: {{ row: 1, col: 2 }},
    legend: {{ x: 24, y: 2, width: 2, values: [-1, 0, 1, 2] }}
  }});
  assertPixel(frame, 24, 2, [147, 197, 253], "legend negative");
  assertPixel(frame, 24, 3, [248, 250, 252], "legend zero");
  assertPixel(frame, 24, 4, [252, 165, 165], "legend positive");
  assertPixel(frame, 24, 5, [220, 38, 38], "legend high positive");
}});

record("ppm-metadata", () => {{
  const frame = renderRaster({{
    width: 28,
    height: 18,
    background: "#111318",
    grid: {{ x: 2, y: 3, cell: 4, gap: 2 }},
    values: [[-1, 0, null, 2], [0, 1, 2, -1], [null, 1, 0, 2]],
    selected: {{ row: 1, col: 2 }},
    alert: {{ row: 1, col: 2 }},
    legend: {{ x: 24, y: 2, width: 2, values: [-1, 0, 1, 2] }}
  }});
  const lines = exportPpm(frame).trim().split(/\\r?\\n/);
  assertEqual(lines[0], "P3", "ppm magic");
  assertEqual(lines[1], "28 18", "ppm dimensions");
  assertEqual(lines[2], "255", "ppm max");
  const channelCount = lines.slice(3).flatMap((line) => line.trim().split(/\\s+/).filter(Boolean)).length;
  assertEqual(channelCount, 28 * 18 * 3, "ppm channel count");
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
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return [{"id": "node-probe-json", "detail": str(exc)}]
    return parsed


def check_css(root: Path, contract: dict):
    css = (root / "candidate" / "workspace" / "src" / "console.css").read_text(encoding="utf-8")
    missing = [marker for marker in contract["required_css_markers"] if marker not in css]
    if missing:
        return [{"id": "css-stability", "detail": ", ".join(missing)}]
    return []


def contains_all(text: str, markers: list[str]):
    lower = text.lower()
    return all(marker.lower() in lower for marker in markers)


def evaluate_ledger(root: Path, contract: dict):
    try:
        ledger = load_json(root / "candidate" / "workspace" / "implementation-ledger.json")
    except Exception as exc:  # noqa: BLE001
        return [{"id": "ledger-complete", "detail": f"invalid JSON: {exc}"}]
    text = json.dumps(ledger, sort_keys=True)
    phase_ids = {item.get("id") or item.get("phaseId") for item in ledger.get("phases", []) if isinstance(item, dict)}
    phase_owners = [
        item for item in ledger.get("phases", [])
        if isinstance(item, dict) and (item.get("owner") or item.get("ownerPath"))
    ]
    if ledger.get("contractId") != contract["contractId"]:
        return [{"id": "ledger-complete", "detail": "contractId mismatch"}]
    if ledger.get("planFingerprint") != contract["planFingerprint"]:
        return [{"id": "ledger-complete", "detail": "plan fingerprint missing"}]
    if set(contract["expectedPhaseIds"]) - phase_ids or len(phase_owners) < len(contract["expectedPhaseIds"]):
        return [{"id": "ledger-complete", "detail": "phase ids or owners incomplete"}]
    if not contains_all(text, contract["expectedSourceIds"]):
        return [{"id": "ledger-complete", "detail": "source ids incomplete"}]
    if not contains_all(text, contract["requiredLedgerMarkers"]):
        return [{"id": "ledger-complete", "detail": "required ledger markers incomplete"}]
    return []


def evaluate_closure(root: Path, contract: dict):
    try:
        closure = load_json(root / "candidate" / "workspace" / "closure.json")
    except Exception as exc:  # noqa: BLE001
        return [{"id": "closure-complete", "detail": f"invalid JSON: {exc}"}]
    text = json.dumps(closure, sort_keys=True)
    if closure.get("contractId") != contract["contractId"]:
        return [{"id": "closure-complete", "detail": "contractId mismatch"}]
    if closure.get("planFingerprint") != contract["planFingerprint"]:
        return [{"id": "closure-complete", "detail": "plan fingerprint missing"}]
    if sorted(closure.get("changedPaths", [])) != sorted(contract["requiredChangedPaths"]):
        return [{"id": "closure-complete", "detail": "changed paths mismatch"}]
    if not closure.get("outcome") or "residualRisk" not in closure:
        return [{"id": "closure-complete", "detail": "outcome or residualRisk missing"}]
    if not contains_all(text, contract["requiredLedgerMarkers"][-3:]):
        return [{"id": "closure-complete", "detail": "validation markers incomplete"}]
    if not contains_all(text, contract["requiredClosureMarkers"]):
        return [{"id": "closure-complete", "detail": "closure markers incomplete"}]
    return []


def run_direct_tests(root: Path, errors: list[str]):
    workspace = root / "candidate" / "workspace"
    result = subprocess.run(["node", "tests/console-contract.test.mjs"], cwd=workspace, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part).strip()
        errors.append(f"Direct tests failed: {output or 'no output'}")


def check_no_hardcoding(root: Path, contract: dict, errors: list[str]):
    terms = [term.lower() for term in contract["prohibited_candidate_terms"]]
    for rel_path in contract["expected_metadata"]["allowed_change_surface"]:
        if not (rel_path.endswith(".mjs") or rel_path.endswith(".css")):
            continue
        text = (root / rel_path).read_text(encoding="utf-8", errors="replace").lower()
        for term in terms:
            if term in text:
                errors.append(f"Candidate file {rel_path} contains prohibited literal: {term}")


def evaluate_bundle(root: Path, contract: dict):
    failures = []
    failures.extend(run_node_probe(root))
    failures.extend(check_css(root, contract))
    failures.extend(evaluate_ledger(root, contract))
    failures.extend(evaluate_closure(root, contract))
    return failures


def write_metrics(path: Path | None, failures: list[dict], errors: list[str] | None = None):
    if path is None:
        return
    error_ids = []
    for error in errors or []:
        if error.startswith("Direct tests failed"):
            error_ids.append("direct-tests")
        elif "prohibited literal" in error:
            error_ids.append("hardcoding")
        else:
            error_ids.append("verifier-error")
    payload = {
        "failure_ids": sorted({failure.get("id", "unknown") for failure in failures} | set(error_ids)),
        "failures": failures,
        "errors": errors or [],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    errors: list[str] = []

    if not root.exists():
        print(f"Bundle root does not exist: {root}", file=sys.stderr)
        return 1

    contract = load_json(root / "oracle" / "ui-visual-state-contract.json")
    check_shape(root, contract, errors)
    if errors:
        write_metrics(args.metrics_out, [], errors)
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if args.bundle_shape_only:
        print("N60 verifier PASS (bundle shape)")
        return 0

    failures = evaluate_bundle(root, contract)
    write_metrics(args.metrics_out, failures)
    if args.expect_start_state:
        expected = set(contract["expected_start_state_failures"])
        observed = {failure["id"] for failure in failures}
        if observed != expected:
            print(f"ERROR: expected start-state failures {sorted(expected)}, found {sorted(observed)}", file=sys.stderr)
            for failure in failures:
                print(f"Observed start failure: {failure['id']} :: {failure.get('detail', '')}", file=sys.stderr)
            return 1
        print("N60 verifier PASS (expected start-state failures present)")
        return 0

    if failures:
        for failure in failures:
            print(f"Failed invariant: {failure['id']} :: {failure.get('detail', '')}", file=sys.stderr)
        return 1

    run_direct_tests(root, errors)
    check_no_hardcoding(root, contract, errors)
    if errors:
        write_metrics(args.metrics_out, failures, errors)
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    write_metrics(args.metrics_out, [], [])
    print("N60 verifier PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
