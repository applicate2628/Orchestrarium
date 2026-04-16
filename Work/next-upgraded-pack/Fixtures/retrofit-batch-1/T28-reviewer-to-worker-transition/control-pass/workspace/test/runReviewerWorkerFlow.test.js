const test = require("node:test");
const assert = require("node:assert/strict");

const { deriveFindings } = require("../src/review/deriveFindings");
const { convertReviewToPatchPlan } = require("../src/worker/convertReviewToPatchPlan");
const { runReviewerWorkerFlow } = require("../src/runReviewerWorkerFlow");

test("keeps the real source finding ahead of docs and legacy echoes", () => {
  const findings = deriveFindings();

  assert.equal(findings[0].id, "F1");
  assert.equal(findings[0].file, "workspace/src/routing/lanePriorityResolver.js");
});

test("converts the main review into a patch plan for the owning source file", () => {
  const plan = convertReviewToPatchPlan(deriveFindings(), "F1");

  assert.equal(plan.findingId, "F1");
  assert.equal(plan.targetFile, "workspace/src/routing/lanePriorityResolver.js");
});

test("stays generic across more than one review finding family", () => {
  const result = runReviewerWorkerFlow({
    reviewSet: "feature",
    requestedFindingId: "F3",
  });

  assert.equal(result.patchPlan.findingId, "F3");
  assert.equal(
    result.patchPlan.targetFile,
    "workspace/src/feature-space/routing/lanePriorityResolver.js"
  );
});

test("preserves the same finding id through the full reviewer-to-worker flow", () => {
  const result = runReviewerWorkerFlow({
    reviewSet: "main",
    requestedFindingId: "F1",
  });

  assert.equal(result.patchPlan.findingId, "F1");
  assert.equal(result.patchPlan.targetFile, "workspace/src/routing/lanePriorityResolver.js");
  assert.deepEqual(result.patchPlan.verificationCommands, [
    "npm test",
    "node scripts/verify-reviewer-worker.js",
  ]);
});
