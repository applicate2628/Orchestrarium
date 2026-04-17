const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const { runFallbackReview } = require("../src/runFallbackReview");

function read(relativePath) {
  return fs.readFileSync(path.join(__dirname, "..", relativePath), "utf8");
}

try {
  const admitted = runFallbackReview({
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

  assert.equal(admitted.selectedRowId, "X2");
  assert.equal(admitted.overlayDecision, "O04");

  const none = runFallbackReview({
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

  assert.equal(none.selectedRowId, null);

  assert.match(read("docs/fallback-overlay.md"), /historical overlay only/);
  assert.match(read("legacy/selectAdmittedSignal.js"), /status === "PASS" \|\| candidate\.notesState === "looks-pass-like"/);
  assert.match(read("reports/noisy-fallback-pass.md"), /looks green at a glance but lacks verifier closure/);

  console.log("VERIFY_T31_FALLBACK_OK");
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
