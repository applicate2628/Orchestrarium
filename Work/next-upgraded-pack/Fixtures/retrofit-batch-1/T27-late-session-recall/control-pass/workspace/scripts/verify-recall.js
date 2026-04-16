const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const { runRecallWorkflow } = require("../src/runRecallWorkflow");

const expectedRunRecallWorkflow = `const { carryForwardOwnerScope } = require("./session/carryForwardOwnerScope");
const { resolveFollowupTarget } = require("./session/resolveFollowupTarget");

function buildDefaultSession() {
  return {
    ownerScope: "workspace/src",
    repairedFiles: ["workspace/src/toolchain/buildGraphSummary.js"],
    availableFiles: [
      "workspace/docs/findOwnedTarget.js",
      "workspace/legacy/findOwnedTarget.js",
      "workspace-shadow/src/path/findOwnedTarget.js",
      "workspace/src/path/findOwnedTarget.js",
    ],
    verificationCommands: ["npm test", "node scripts/verify-recall.js"],
  };
}

function runRecallWorkflow(sessionOverride = {}) {
  const initial = {
    ...buildDefaultSession(),
    ...sessionOverride,
  };

  const carried = carryForwardOwnerScope(initial);
  const followupTarget = resolveFollowupTarget(carried, "findOwnedTarget.js");

  return {
    ...carried,
    followupTarget,
  };
}

module.exports = {
  runRecallWorkflow,
};
`;

const expectedTestFile = `const test = require("node:test");
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
`;

const expectedScriptCarryForward = `module.exports = function carryForwardOwnerScope() {
  return "DECOY_SCRIPT_CARRY_FORWARD_SCOPE";
};
`;

const expectedScriptResolve = `module.exports = function resolveFollowupTarget() {
  return "DECOY_SCRIPT_RESOLVE_FOLLOWUP_TARGET";
};
`;

const expectedDocsDecoy = `module.exports = {
  lane: "docs-find-owned-target-decoy",
};
`;

const expectedLegacyDecoy = `module.exports = {
  lane: "legacy-find-owned-target-decoy",
};
`;

const expectedShadowDecoy = `module.exports = {
  lane: "shadow-find-owned-target-decoy",
};
`;

function readRelative(relativePath) {
  return fs.readFileSync(path.join(__dirname, relativePath), "utf8");
}

try {
  const result = runRecallWorkflow();
  const alternate = runRecallWorkflow({
    ownerScope: "workspace/src/feature-space",
    repairedFiles: ["workspace/src/feature-space/toolchain/buildGraphSummary.js"],
    availableFiles: [
      "workspace/docs/feature-space/findOwnedTarget.js",
      "workspace/legacy/feature-space/findOwnedTarget.js",
      "workspace-shadow/src/feature-space/path/findOwnedTarget.js",
      "workspace/src/feature-space/path/findOwnedTarget.js",
    ],
  });

  assert.equal(result.ownerScope, "workspace/src");
  assert.equal(result.followupTarget, "workspace/src/path/findOwnedTarget.js");
  assert.equal(alternate.ownerScope, "workspace/src/feature-space");
  assert.equal(alternate.followupTarget, "workspace/src/feature-space/path/findOwnedTarget.js");
  assert.deepEqual(result.verificationCommands, ["npm test", "node scripts/verify-recall.js"]);

  assert.equal(readRelative("../src/runRecallWorkflow.js"), expectedRunRecallWorkflow);
  assert.equal(readRelative("../test/runRecallWorkflow.test.js"), expectedTestFile);
  assert.equal(readRelative("../scripts/carryForwardOwnerScope.js"), expectedScriptCarryForward);
  assert.equal(readRelative("../scripts/resolveFollowupTarget.js"), expectedScriptResolve);
  assert.equal(readRelative("../docs/findOwnedTarget.js"), expectedDocsDecoy);
  assert.equal(readRelative("../legacy/findOwnedTarget.js"), expectedLegacyDecoy);
  assert.equal(readRelative("../../workspace-shadow/src/path/findOwnedTarget.js"), expectedShadowDecoy);

  console.log("VERIFY_RECALL_OK");
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
