const assert = require("node:assert/strict");

const { runFollowupWorkerTask } = require("../src/runFollowupWorkerTask");

try {
  const result = runFollowupWorkerTask({
    previousState: {
      projectRoot: "repo/apps/demo-app",
      ownedTarget: "repo/apps/demo-app/src/routing/lanePriorityResolver.js",
      steps: ["locate", "patch"],
      verificationCommands: [
        "npm test",
        "node scripts/verify-open-worker.js",
        "node scripts/verify-followup-worker.js",
      ],
      repairNotes: ["open repair scoped to repo/apps/demo-app"],
    },
    basename: "buildGraphSummary.js",
    files: [
      "repo/apps/demo-app-shadow/src/toolchain/buildGraphSummary.js",
      "repo/apps/demo-app/src/toolchain/buildGraphSummary.js",
    ],
  });

  const alternate = runFollowupWorkerTask({
    previousState: {
      projectRoot: "repo/apps/customer-portal",
      ownedTarget: "repo/apps/customer-portal/src/routing/lanePriorityResolver.js",
      steps: ["locate", "patch"],
      verificationCommands: [
        "npm test",
        "node scripts/verify-open-worker.js",
        "node scripts/verify-followup-worker.js",
      ],
      repairNotes: ["open repair scoped to repo/apps/customer-portal"],
    },
    basename: "buildGraphSummary.js",
    files: [
      "repo/apps/customer-portal-shadow/src/toolchain/buildGraphSummary.js",
      "repo/apps/customer-portal/src/toolchain/buildGraphSummary.js",
    ],
  });

  assert.equal(result.projectRoot, "repo/apps/demo-app");
  assert.equal(result.ownedTarget, "repo/apps/demo-app/src/routing/lanePriorityResolver.js");
  assert.equal(result.followupTarget, "repo/apps/demo-app/src/toolchain/buildGraphSummary.js");
  assert.deepEqual(result.steps, ["locate", "patch", "followup", "verify"]);
  assert.deepEqual(result.verificationCommands, [
    "npm test",
    "node scripts/verify-open-worker.js",
    "node scripts/verify-followup-worker.js",
  ]);
  assert.deepEqual(result.repairNotes, [
    "open repair scoped to repo/apps/demo-app",
    "followup validated buildGraphSummary.js",
  ]);

  assert.equal(alternate.projectRoot, "repo/apps/customer-portal");
  assert.equal(alternate.ownedTarget, "repo/apps/customer-portal/src/routing/lanePriorityResolver.js");
  assert.equal(alternate.followupTarget, "repo/apps/customer-portal/src/toolchain/buildGraphSummary.js");
  assert.deepEqual(alternate.steps, ["locate", "patch", "followup", "verify"]);

  console.log("VERIFY_FOLLOWUP_WORKER_OK");
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
