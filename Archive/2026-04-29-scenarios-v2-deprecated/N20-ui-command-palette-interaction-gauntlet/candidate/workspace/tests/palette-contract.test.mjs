import assert from "node:assert/strict";
import { renderPalette } from "../src/command-palette.mjs";
import {
  applyFilter,
  clearFilter,
  createPaletteState,
  moveFocus,
  selectActive,
} from "../src/palette-state.mjs";

const actions = [
  { id: "open", label: "Open build report", owner: "qa", returnCue: "Return to report list" },
  { id: "deploy", label: "Deploy release candidate", owner: "release", returnCue: "Return to release lane" },
  { id: "delete", label: "Delete production cache", owner: "security", returnCue: "Return to cache review", disabled: true },
  { id: "rollback", label: "Rollback failed deployment", owner: "release", returnCue: "Return to incident timeline" },
];

let state = createPaletteState(actions);
state = moveFocus(state, "down");
assert.equal(state.activeId, "deploy");
state = moveFocus(state, "down");
assert.equal(state.activeId, "rollback");
state = moveFocus(state, "down");
assert.equal(state.activeId, "open");

state = { ...state, activeId: "deploy", lastStableActiveId: "deploy" };
state = applyFilter(state, "deploy");
assert.equal(state.activeId, "deploy");
state = clearFilter(state);
assert.equal(state.activeId, "deploy");

const disabledState = { ...state, activeId: "delete" };
assert.equal(selectActive(disabledState).selected, null);

const html = renderPalette(state);
assert.match(html, /role="listbox"/);
assert.match(html, /aria-activedescendant="palette-option-deploy"/);
assert.match(html, /id="palette-option-deploy"/);
assert.match(html, /data-visible-return-cue="Return to release lane"/);
