const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function read(relativePath) {
  return fs.readFileSync(path.join(__dirname, "..", relativePath), "utf8");
}

function readJson(relativePath) {
  return JSON.parse(read(relativePath));
}

try {
  const answer = readJson("out/ui-triage.json");

  assert.deepEqual(answer, {
    blockingIssues: [
      "note-anchored-to-container-not-row",
      "hidden-note-stays-in-keyboard-order",
      "inline-note-uses-modal-semantics",
    ],
    fixOrder: [
      "fix-row-anchoring",
      "respect-hidden-and-remove-from-keyboard-order",
      "change-dialog-semantics-and-ranking-copy",
    ],
    doNotUseAsSingleFix: "z-index-only",
  });

  const notes = read("inputs/triage-notes.md");
  const contract = read("inputs/interaction-contract.md");
  assert.match(notes, /z-index: 9999/);
  assert.match(contract, /must not overwrite the row order with a global winner claim/);

  console.log("VERIFY_T18_UI_TRIAGE_OK");
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
