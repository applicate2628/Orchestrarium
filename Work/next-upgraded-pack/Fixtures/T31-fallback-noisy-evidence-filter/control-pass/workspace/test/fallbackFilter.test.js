const test = require("node:test");
const assert = require("node:assert/strict");

const { runFallbackReview } = require("../src/runFallbackReview");

test("verifier-backed admitted evidence beats noisy raw notes", () => {
  const result = runFallbackReview({
    candidates: [
      {
        rowId: "X6",
        source: "raw-notes",
        status: "PASS",
        verifierPassed: false,
        notesState: "looks-pass-like",
        overlayLevel: "O05",
        evidenceWeight: 1,
      },
      {
        rowId: "X2",
        source: "admitted-run",
        status: "PASS",
        verifierPassed: true,
        notesState: "clean",
        overlayLevel: "O04",
        evidenceWeight: 3,
      },
    ],
  });

  assert.equal(result.selectedRowId, "X2");
  assert.equal(result.overlayDecision, "O04");
});

test("no verifier-backed pass means no admission", () => {
  const result = runFallbackReview({
    candidates: [
      {
        rowId: "X6",
        source: "raw-notes",
        status: "PASS",
        verifierPassed: false,
        notesState: "looks-pass-like",
        overlayLevel: "O05",
        evidenceWeight: 1,
      },
      {
        rowId: "X2",
        source: "stale-summary",
        status: "FAIL",
        verifierPassed: false,
        notesState: "noisy",
        overlayLevel: "O04",
        evidenceWeight: 3,
      },
    ],
  });

  assert.equal(result.selectedRowId, null);
  assert.equal(result.overlayDecision, "no-admission");
});

test("among admitted rows, stronger evidence wins even when it appears later", () => {
  const result = runFallbackReview({
    candidates: [
      {
        rowId: "X6",
        source: "admitted-run",
        status: "PASS",
        verifierPassed: true,
        notesState: "clean",
        overlayLevel: "O05",
        evidenceWeight: 2,
      },
      {
        rowId: "X2",
        source: "admitted-run",
        status: "PASS",
        verifierPassed: true,
        notesState: "clean",
        overlayLevel: "O04",
        evidenceWeight: 3,
      },
    ],
  });

  assert.equal(result.selectedRowId, "X2");
  assert.equal(result.overlayDecision, "O04");
});
