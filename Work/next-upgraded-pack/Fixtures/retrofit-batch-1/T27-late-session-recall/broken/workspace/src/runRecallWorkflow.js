const { carryForwardOwnerScope } = require("./session/carryForwardOwnerScope");
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
