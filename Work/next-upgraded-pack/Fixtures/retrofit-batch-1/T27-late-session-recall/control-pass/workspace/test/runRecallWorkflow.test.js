const test = require("node:test");
const assert = require("node:assert/strict");

const { carryForwardOwnerScope } = require("../src/session/carryForwardOwnerScope");
const { resolveFollowupTarget } = require("../src/session/resolveFollowupTarget");
const { runRecallWorkflow } = require("../src/runRecallWorkflow");

test("preserves an explicitly broader owner scope across later steps", () => {
  const carried = carryForwardOwnerScope({
    ownerScope: "workspace/src",
    repairedFiles: ["workspace/src/toolchain/buildGraphSummary.js"],
  });

  assert.equal(carried.ownerScope, "workspace/src");
});

test("resolves the follow-up target inside the preserved source scope", () => {
  const target = resolveFollowupTarget(
    {
      ownerScope: "workspace/src",
      availableFiles: [
        "workspace/docs/findOwnedTarget.js",
        "workspace/legacy/findOwnedTarget.js",
        "workspace-shadow/src/path/findOwnedTarget.js",
        "workspace/src/path/findOwnedTarget.js",
      ],
    },
    "findOwnedTarget.js"
  );

  assert.equal(target, "workspace/src/path/findOwnedTarget.js");
});

test("stays generic across more than one source scope", () => {
  const result = runRecallWorkflow({
    ownerScope: "workspace/src/feature-space",
    repairedFiles: ["workspace/src/feature-space/toolchain/buildGraphSummary.js"],
    availableFiles: [
      "workspace/docs/feature-space/findOwnedTarget.js",
      "workspace/legacy/feature-space/findOwnedTarget.js",
      "workspace-shadow/src/feature-space/path/findOwnedTarget.js",
      "workspace/src/feature-space/path/findOwnedTarget.js",
    ],
  });

  assert.equal(result.ownerScope, "workspace/src/feature-space");
  assert.equal(result.followupTarget, "workspace/src/feature-space/path/findOwnedTarget.js");
});

test("builds a coherent recall workflow without drifting to decoys", () => {
  const result = runRecallWorkflow();

  assert.equal(result.ownerScope, "workspace/src");
  assert.equal(result.followupTarget, "workspace/src/path/findOwnedTarget.js");
  assert.deepEqual(result.verificationCommands, ["npm test", "node scripts/verify-recall.js"]);
});
