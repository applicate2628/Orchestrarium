import assert from "node:assert/strict";
import {
  applyCommandFilter,
  attemptRecordNavigation,
  createConsoleState,
  isDirty,
  moveCommandFocus,
  saveActiveRecord,
  selectActiveCommand,
  updateDraftField
} from "../src/console-state.mjs";
import { renderConsole } from "../src/console-view.mjs";
import { computeLayout } from "../src/console-layout.mjs";
import { exportPpm, renderRaster } from "../src/console-raster.mjs";

const records = [
  {
    id: "api-17",
    label: "API Incident",
    owner: "incident",
    baseline: { title: "API incident", slug: "api-incident", severity: "high", summary: "Queue API retry storm" }
  },
  {
    id: "billing-29",
    label: "Billing Review",
    owner: "finance",
    baseline: { title: "Billing review", slug: "billing-review", severity: "medium", summary: "Invoice queue drift" }
  }
];

const commands = [
  { id: "approve", group: "triage", label: "Approve rollback", owner: "incident", returnCue: "Return to incident queue" },
  { id: "approve", group: "security", label: "Approve firewall exception", owner: "security", returnCue: "Return to security queue", disabled: true },
  { id: "inspect", group: "ops", label: "Inspect deployment health", owner: "ops", returnCue: "Return to deployment health" }
];

let state = createConsoleState(records, commands);
state = moveCommandFocus(state, "down");
assert.equal(state.activeCommandKey, "ops:inspect");

state = createConsoleState(records, commands);
state = updateDraftField(state, "title", "API draft");
state = attemptRecordNavigation(state, "billing-29");
assert.equal(state.activeRecordId, "api-17");
assert.equal(isDirty(state, "api-17"), true);
assert.equal(state.blockedNavigation.targetId, "billing-29");

state = updateDraftField(state, "slug", "Bad Slug!");
state = saveActiveRecord(state, { ok: true });
assert.equal(isDirty(state, "api-17"), true);
assert.ok(state.records[0].errors.slug);

const html = renderConsole(state);
assert.match(html, /role="listbox"/);
assert.match(html, /aria-live="polite"/);
assert.match(html, /aria-invalid="true"/);

const layout = computeLayout({ width: 320, height: 640 }, state);
assert.ok(layout.boxes.every((box) => box.x >= 0 && box.x + box.width <= 320));

const frame = renderRaster({
  width: 28,
  height: 18,
  background: "#111318",
  grid: { x: 2, y: 3, cell: 4, gap: 2 },
  values: [[-1, 0, null, 2], [0, 1, 2, -1], [null, 1, 0, 2]],
  selected: { row: 1, col: 2 },
  legend: { x: 24, y: 2, width: 2, values: [-1, 0, 1, 2] }
});
assert.deepEqual(frame[4][15], [17, 19, 24]);
assert.match(exportPpm(frame).split("\n").slice(0, 3).join("\n"), /^P3\n28 18\n255$/);

state = applyCommandFilter(createConsoleState(records, commands), "approve");
assert.equal(selectActiveCommand(state).selected.owner, "incident");
