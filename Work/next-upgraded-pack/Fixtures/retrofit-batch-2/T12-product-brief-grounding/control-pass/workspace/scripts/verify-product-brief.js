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
  const answer = readJson("out/product-brief.json");

  assert.deepEqual(answer, {
    primaryAudience: "operators",
    deliverableMode: "read-only-reporting",
    preserveLaneSpecificRankings: true,
    rejectGlobalProviderWinner: true,
    firstSlice: "compact-lane-specific-provider-summary-with-fallback-notes",
    openQuestions: [
      "which-audience-is-first-operators-or-contributors",
      "is-the-first-deliverable-read-only-reporting-or-editable-policy-tuning",
    ],
  });

  const notes = read("inputs/intake-notes.md");
  assert.match(notes, /the benchmark screen is confusing/);
  assert.match(notes, /single global provider rank/);

  console.log("VERIFY_T12_PRODUCT_BRIEF_OK");
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
