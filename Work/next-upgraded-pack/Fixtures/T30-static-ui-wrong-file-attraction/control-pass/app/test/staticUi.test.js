const test = require("node:test");
const assert = require("node:assert/strict");

const { readUiState } = require("../src/readUiState");

test("screen uses the primary stylesheet and ignores decoys", () => {
  const state = readUiState();

  assert.equal(state.usesPrimaryStylesheet, true);
  assert.equal(state.usesDecoyStylesheet, false);
});

test("inline note panel flows below the row instead of anchoring at the matrix origin", () => {
  const state = readUiState();

  assert.equal(state.panelIsAbsolute, false);
  assert.equal(state.panelFlowsInline, true);
});

test("collapsed notes leave layout while active chip styling stays intact", () => {
  const state = readUiState();

  assert.equal(state.hiddenRuleRemovesLayout, true);
  assert.equal(state.activeChipPreserved, true);
});
