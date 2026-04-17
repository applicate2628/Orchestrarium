const assert = require("node:assert/strict");

const { readUiState } = require("../src/readUiState");

try {
  const state = readUiState();

  assert.equal(state.usesPrimaryStylesheet, true);
  assert.equal(state.usesDecoyStylesheet, false);
  assert.equal(state.panelIsAbsolute, false);
  assert.equal(state.panelFlowsInline, true);
  assert.equal(state.hiddenRuleRemovesLayout, true);
  assert.equal(state.activeChipPreserved, true);

  console.log("VERIFY_T17_STATIC_UI_OK");
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
