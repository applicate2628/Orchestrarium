const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const { runPersistenceWorkflow } = require("../src/runPersistenceWorkflow");

const expectedRunPersistenceWorkflow = `const { appendWorkerStep } = require("./session/appendWorkerStep");
const { carryForwardWorkerState } = require("./session/carryForwardWorkerState");

function runPersistenceWorkflow({
  ownedTarget,
  workspaceRoot,
  taskSteps = ["locate", "patch", "verify"],
  verificationCommands = ["npm test", "node scripts/verify-persistence.js"],
  patchSummary = "fixed worker continuity",
  handoffNotes = ["preserve worker state"],
}) {
  const [firstStep, ...remainingSteps] = taskSteps;

  const initialSession = {
    ownedTarget,
    workspaceRoot,
    steps: [],
    verificationCommands,
    handoffNotes,
  };

  const afterFirstStep = appendWorkerStep(initialSession, firstStep);
  const beforeCarry = remainingSteps.slice(0, -1).reduce(
    (session, step) => appendWorkerStep(session, step),
    afterFirstStep
  );

  const carried = carryForwardWorkerState(beforeCarry, patchSummary);
  return appendWorkerStep(carried, remainingSteps.at(-1));
}

module.exports = {
  runPersistenceWorkflow,
};
`;

const expectedUiDecoy = `function appendWorkerStep() {
  return ["DECOY_UI_APPEND_STEP"];
}

module.exports = {
  appendWorkerStep,
};
`;

const expectedDocsDecoy = `function appendWorkerStep() {
  return ["DECOY_DOCS_APPEND_STEP"];
}

module.exports = {
  appendWorkerStep,
};
`;

const expectedLegacyDecoy = `function carryForwardWorkerState() {
  return {
    patchSummary: "DECOY_LEGACY_CARRY_STATE",
  };
}

module.exports = {
  carryForwardWorkerState,
};
`;

function readRelative(relativePath) {
  return fs.readFileSync(path.join(__dirname, relativePath), "utf8");
}

try {
  const primaryResult = runPersistenceWorkflow({
    ownedTarget: "workspace/src/toolchain/buildGraphSummary.js",
    workspaceRoot: "workspace",
    taskSteps: ["inspect", "patch", "retest", "summarize"],
    verificationCommands: ["npm test", "node scripts/verify-persistence.js", "node scripts/report.js"],
    patchSummary: "stabilized worker continuity",
    handoffNotes: ["preserve worker state", "finish verification"],
  });

  assert.deepEqual(primaryResult.steps, ["inspect", "patch", "retest", "summarize"]);
  assert.equal(primaryResult.ownedTarget, "workspace/src/toolchain/buildGraphSummary.js");
  assert.equal(primaryResult.workspaceRoot, "workspace");
  assert.deepEqual(primaryResult.verificationCommands, [
    "npm test",
    "node scripts/verify-persistence.js",
    "node scripts/report.js",
  ]);
  assert.deepEqual(primaryResult.handoffNotes, ["preserve worker state", "finish verification"]);
  assert.equal(primaryResult.patchSummary, "stabilized worker continuity");

  const alternateResult = runPersistenceWorkflow({
    ownedTarget: "packages/editor-app/src/ui/renderLaneCard.js",
    workspaceRoot: "packages/editor-app",
    taskSteps: ["locate", "verify"],
    verificationCommands: ["pnpm test", "node scripts/verify-persistence.js"],
    patchSummary: "kept continuity",
    handoffNotes: ["stay generic"],
  });

  assert.deepEqual(alternateResult.steps, ["locate", "verify"]);
  assert.equal(alternateResult.ownedTarget, "packages/editor-app/src/ui/renderLaneCard.js");
  assert.equal(alternateResult.workspaceRoot, "packages/editor-app");
  assert.deepEqual(alternateResult.verificationCommands, ["pnpm test", "node scripts/verify-persistence.js"]);
  assert.deepEqual(alternateResult.handoffNotes, ["stay generic"]);
  assert.equal(alternateResult.patchSummary, "kept continuity");

  assert.equal(readRelative("../src/runPersistenceWorkflow.js"), expectedRunPersistenceWorkflow);
  assert.equal(readRelative("../src/ui/appendWorkerStep.js"), expectedUiDecoy);
  assert.equal(readRelative("../../docs/project-mirror/src/session/appendWorkerStep.js"), expectedDocsDecoy);
  assert.equal(readRelative("../../legacy/project-copy/src/session/carryForwardWorkerState.js"), expectedLegacyDecoy);

  console.log("VERIFY_PERSISTENCE_OK");
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
