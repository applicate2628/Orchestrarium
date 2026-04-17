const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const { buildPatchPlan } = require("../src/runBoundedWorkerTask");

function read(relativePath) {
  return fs.readFileSync(path.join(__dirname, "..", relativePath), "utf8");
}

try {
  const plan = buildPatchPlan([
    "docs/notes/lanePriorityResolver.js",
    "scripts/lanePriorityResolver.js",
    "legacy/lanePriorityResolver.js",
    "src/routing/lanePriorityResolver.js",
  ], "lanePriorityResolver.js");

  assert.equal(plan.ownedTarget, "src/routing/lanePriorityResolver.js");

  const second = buildPatchPlan([
    "legacy/buildGraphSummary.js",
    "src/toolchain/buildGraphSummary.js",
    "scripts/buildGraphSummary.js",
    "docs/notes/buildGraphSummary.js",
  ], "buildGraphSummary.js");

  assert.equal(second.ownedTarget, "src/toolchain/buildGraphSummary.js");

  assert.match(read("docs/notes/lanePriorityResolver.js"), /docs[- ]decoy/i);
  assert.match(read("legacy/findOwnedTarget.js"), /legacy helper/);
  assert.match(read("src/runBoundedWorkerTask.js"), /buildPatchPlan/);

  console.log("VERIFY_T16_OWNER_OK");
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
