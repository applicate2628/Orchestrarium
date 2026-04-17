const test = require("node:test");
const assert = require("node:assert/strict");

const { buildPatchPlan } = require("../src/runBoundedWorkerTask");
const { findOwnedTarget } = require("../src/path/findOwnedTarget");

test("prefers the src owner over docs, scripts, and legacy decoys", () => {
  const files = [
    "docs/notes/lanePriorityResolver.js",
    "scripts/lanePriorityResolver.js",
    "legacy/lanePriorityResolver.js",
    "src/routing/lanePriorityResolver.js",
  ];

  const plan = buildPatchPlan(files, "lanePriorityResolver.js");

  assert.equal(plan.ownedTarget, "src/routing/lanePriorityResolver.js");
  assert.deepEqual(plan.patchSurface, ["src/routing/lanePriorityResolver.js"]);
});

test("stays generic across a second basename instead of hardcoding one path", () => {
  const files = [
    "legacy/buildGraphSummary.js",
    "src/toolchain/buildGraphSummary.js",
    "scripts/buildGraphSummary.js",
    "docs/notes/buildGraphSummary.js",
  ];

  const plan = buildPatchPlan(files, "buildGraphSummary.js");

  assert.equal(plan.ownedTarget, "src/toolchain/buildGraphSummary.js");
});

test("normalizes Windows separators before selecting the owner", () => {
  const files = [
    "docs\\notes\\lanePriorityResolver.js",
    "scripts\\lanePriorityResolver.js",
    "src\\routing\\lanePriorityResolver.js",
  ];

  assert.equal(findOwnedTarget(files, "lanePriorityResolver.js"), "src/routing/lanePriorityResolver.js");
});

test("returns null when there is no matching owner candidate", () => {
  assert.equal(findOwnedTarget(["docs/notes/noise.js"], "missingOwner.js"), null);
});
