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
    nextMilestone: "complete-full-registry-execution-for-x1-x3",
    topPriority: [
      "build-remaining-extended-fixtures",
      "run-extended-batch-for-x1-x3",
      "refresh-full-registry-results",
    ],
    deferSamePass: ["gemini-runtime-hardening", "archive-admission"],
    goalType: "bounded-execution-closeout",
    requiresNewRankingSurface: true,
    openQuestions: [],
  });

  const notes = read("inputs/intake-notes.md");
  assert.match(notes, /finish the remaining extended tests and run them/);
  assert.match(notes, /Do not reopen Gemini in the same pass/);

  console.log("VERIFY_T11_PRIORITY_TRIAGE_OK");
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
