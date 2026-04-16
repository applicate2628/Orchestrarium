const test = require("node:test");
const assert = require("node:assert/strict");

const { appendWorkerStep } = require("../src/session/appendWorkerStep");
const { carryForwardWorkerState } = require("../src/session/carryForwardWorkerState");
const { runPersistenceWorkflow } = require("../src/runPersistenceWorkflow");

test("preserves earlier steps instead of replacing them with only the latest one", () => {
  const first = appendWorkerStep({ steps: [] }, "inspect");
  const second = appendWorkerStep(first, "patch");
  const third = appendWorkerStep(second, "retest");

  assert.deepEqual(third.steps, ["inspect", "patch", "retest"]);
});

test("keeps worker state while carrying patch state forward", () => {
  const carried = carryForwardWorkerState(
    {
      ownedTarget: "workspace/src/toolchain/buildGraphSummary.js",
      workspaceRoot: "workspace",
      steps: ["inspect", "patch", "retest"],
      verificationCommands: ["npm test", "node scripts/verify-persistence.js", "node scripts/report.js"],
      handoffNotes: ["preserve worker state", "finish verification"],
    },
    "stabilized worker continuity"
  );

  assert.equal(carried.ownedTarget, "workspace/src/toolchain/buildGraphSummary.js");
  assert.equal(carried.workspaceRoot, "workspace");
  assert.deepEqual(carried.steps, ["inspect", "patch", "retest"]);
  assert.deepEqual(carried.verificationCommands, [
    "npm test",
    "node scripts/verify-persistence.js",
    "node scripts/report.js",
  ]);
  assert.deepEqual(carried.handoffNotes, ["preserve worker state", "finish verification"]);
  assert.equal(carried.patchSummary, "stabilized worker continuity");
});

test("builds a coherent four-step workflow without forgetting prior work", () => {
  const result = runPersistenceWorkflow({
    ownedTarget: "workspace/src/toolchain/buildGraphSummary.js",
    workspaceRoot: "workspace",
    taskSteps: ["inspect", "patch", "retest", "summarize"],
    verificationCommands: ["npm test", "node scripts/verify-persistence.js", "node scripts/report.js"],
    patchSummary: "stabilized worker continuity",
    handoffNotes: ["preserve worker state", "finish verification"],
  });

  assert.deepEqual(result.steps, ["inspect", "patch", "retest", "summarize"]);
  assert.equal(result.ownedTarget, "workspace/src/toolchain/buildGraphSummary.js");
  assert.equal(result.workspaceRoot, "workspace");
  assert.deepEqual(result.verificationCommands, [
    "npm test",
    "node scripts/verify-persistence.js",
    "node scripts/report.js",
  ]);
  assert.deepEqual(result.handoffNotes, ["preserve worker state", "finish verification"]);
  assert.equal(result.patchSummary, "stabilized worker continuity");
});

test("stays generic across alternate workspace roots and shorter workflows", () => {
  const result = runPersistenceWorkflow({
    ownedTarget: "packages/editor-app/src/ui/renderLaneCard.js",
    workspaceRoot: "packages/editor-app",
    taskSteps: ["locate", "verify"],
    verificationCommands: ["pnpm test", "node scripts/verify-persistence.js"],
    patchSummary: "kept continuity",
    handoffNotes: ["stay generic"],
  });

  assert.deepEqual(result.steps, ["locate", "verify"]);
  assert.equal(result.ownedTarget, "packages/editor-app/src/ui/renderLaneCard.js");
  assert.equal(result.workspaceRoot, "packages/editor-app");
  assert.deepEqual(result.verificationCommands, ["pnpm test", "node scripts/verify-persistence.js"]);
  assert.deepEqual(result.handoffNotes, ["stay generic"]);
  assert.equal(result.patchSummary, "kept continuity");
});
