const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const { runReviewerWorkerFlow } = require("../src/runReviewerWorkerFlow");

const expectedRunReviewerWorkerFlow = `const { deriveFindings } = require("./review/deriveFindings");
const { convertReviewToPatchPlan } = require("./worker/convertReviewToPatchPlan");

function runReviewerWorkerFlow({ reviewSet = "main", requestedFindingId } = {}) {
  const findings = deriveFindings(reviewSet);
  const patchPlan = convertReviewToPatchPlan(findings, requestedFindingId);

  return {
    reviewSet,
    findings,
    patchPlan,
  };
}

module.exports = {
  runReviewerWorkerFlow,
};
`;

const expectedTestFile = `const test = require("node:test");
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
`;

const expectedScriptDeriveFindings = `module.exports = function deriveFindings() {
  return "DECOY_SCRIPT_DERIVE_FINDINGS";
};
`;

const expectedScriptConvertReview = `module.exports = function convertReviewToPatchPlan() {
  return "DECOY_SCRIPT_CONVERT_REVIEW_TO_PATCH_PLAN";
};
`;

const expectedDocsDecoy = `module.exports = {
  lane: "docs-routing-decoy",
};
`;

const expectedLegacyDecoy = `module.exports = {
  lane: "legacy-routing-decoy",
};
`;

const expectedShadowDecoy = `module.exports = {
  lane: "shadow-routing-decoy",
};
`;

function readRelative(relativePath) {
  return fs.readFileSync(path.join(__dirname, relativePath), "utf8");
}

try {
  const main = runReviewerWorkerFlow({
    reviewSet: "main",
    requestedFindingId: "F1",
  });
  const feature = runReviewerWorkerFlow({
    reviewSet: "feature",
    requestedFindingId: "F3",
  });

  assert.equal(main.patchPlan.findingId, "F1");
  assert.equal(main.patchPlan.targetFile, "workspace/src/routing/lanePriorityResolver.js");
  assert.equal(feature.patchPlan.findingId, "F3");
  assert.equal(feature.patchPlan.targetFile, "workspace/src/feature-space/routing/lanePriorityResolver.js");
  assert.deepEqual(main.patchPlan.verificationCommands, [
    "npm test",
    "node scripts/verify-reviewer-worker.js",
  ]);

  assert.equal(readRelative("../src/runReviewerWorkerFlow.js"), expectedRunReviewerWorkerFlow);
  assert.equal(readRelative("../test/runReviewerWorkerFlow.test.js"), expectedTestFile);
  assert.equal(readRelative("../scripts/deriveFindings.js"), expectedScriptDeriveFindings);
  assert.equal(readRelative("../scripts/convertReviewToPatchPlan.js"), expectedScriptConvertReview);
  assert.equal(readRelative("../docs/lanePriorityResolver.js"), expectedDocsDecoy);
  assert.equal(readRelative("../legacy/lanePriorityResolver.js"), expectedLegacyDecoy);
  assert.equal(readRelative("../../workspace-shadow/src/routing/lanePriorityResolver.js"), expectedShadowDecoy);

  console.log("VERIFY_REVIEWER_WORKER_OK");
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
