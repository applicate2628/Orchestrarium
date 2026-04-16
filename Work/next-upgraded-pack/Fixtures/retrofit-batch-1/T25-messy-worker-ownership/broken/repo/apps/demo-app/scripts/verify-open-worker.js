const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const { runOpenWorkerTask } = require("../src/runOpenWorkerTask");

const expectedRunOpenWorkerTask = `const { findProjectRoot } = require("./workspace/findProjectRoot");
const { findOwnedTarget } = require("./path/findOwnedTarget");

function runOpenWorkerTask({ basename, startDir, manifestFiles, files }) {
  const projectRoot = findProjectRoot(manifestFiles, startDir);
  const ownedTarget = findOwnedTarget(files, basename);

  return {
    projectRoot,
    ownedTarget,
    verificationCommands: [
      "npm test",
      "node scripts/verify-open-worker.js",
      "node scripts/verify-followup-worker.js",
    ],
    repairNotes: [\`open repair scoped to \${projectRoot ?? "unknown-root"}\`],
  };
}

module.exports = {
  runOpenWorkerTask,
};
`;

const expectedRunFollowupWorkerTask = `const { findOwnedTarget } = require("./path/findOwnedTarget");
const { mergeRepairSession } = require("./session/mergeRepairSession");

function runFollowupWorkerTask({ previousState, basename, files }) {
  const followupTarget = findOwnedTarget(files, basename);

  return mergeRepairSession(previousState, {
    followupTarget,
    steps: ["followup", "verify"],
    repairNotes: [\`followup validated \${basename}\`],
  });
}

module.exports = {
  runFollowupWorkerTask,
};
`;

const expectedTestFile = `const test = require("node:test");
const assert = require("node:assert/strict");

const { findProjectRoot } = require("../src/workspace/findProjectRoot");
const { findOwnedTarget } = require("../src/path/findOwnedTarget");
const { mergeRepairSession } = require("../src/session/mergeRepairSession");
const { runOpenWorkerTask } = require("../src/runOpenWorkerTask");
const { runFollowupWorkerTask } = require("../src/runFollowupWorkerTask");

test("finds the real app root instead of a mirrored root", () => {
  assert.equal(
    findProjectRoot(
      [
        "repo/apps/demo-app-shadow/package.json",
        "repo/docs/demo-app/package.json",
        "repo/legacy/demo-app-copy/package.json",
        "repo/apps/demo-app/package.json",
      ],
      "repo/apps/demo-app/src/build"
    ),
    "repo/apps/demo-app"
  );
});

test("finds the real owning source file instead of mirrored copies", () => {
  assert.equal(
    findOwnedTarget(
      [
        "repo/apps/demo-app-shadow/src/toolchain/buildGraphSummary.js",
        "repo/docs/notes/lanePriorityResolver.js",
        "repo/legacy/lanePriorityResolver.js",
        "repo/apps/demo-app/src/toolchain/buildGraphSummary.js",
      ],
      "buildGraphSummary.js"
    ),
    "repo/apps/demo-app/src/toolchain/buildGraphSummary.js"
  );
});

test("preserves prior session state while merging later follow-up state", () => {
  const merged = mergeRepairSession(
    {
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
    {
      followupTarget: "repo/apps/demo-app/src/toolchain/buildGraphSummary.js",
      steps: ["followup", "verify"],
      repairNotes: ["followup validated buildGraphSummary.js"],
    }
  );

  assert.equal(merged.projectRoot, "repo/apps/demo-app");
  assert.equal(merged.ownedTarget, "repo/apps/demo-app/src/routing/lanePriorityResolver.js");
  assert.equal(merged.followupTarget, "repo/apps/demo-app/src/toolchain/buildGraphSummary.js");
  assert.deepEqual(merged.steps, ["locate", "patch", "followup", "verify"]);
  assert.deepEqual(merged.repairNotes, [
    "open repair scoped to repo/apps/demo-app",
    "followup validated buildGraphSummary.js",
  ]);
});

test("builds a coherent open worker plan and follow-up state", () => {
  const open = runOpenWorkerTask({
    basename: "lanePriorityResolver.js",
    startDir: "repo/apps/demo-app/src/build",
    manifestFiles: [
      "repo/apps/demo-app-shadow/package.json",
      "repo/docs/demo-app/package.json",
      "repo/legacy/demo-app-copy/package.json",
      "repo/apps/demo-app/package.json",
    ],
    files: [
      "repo/docs/notes/lanePriorityResolver.js",
      "repo/legacy/lanePriorityResolver.js",
      "repo/apps/demo-app/src/routing/lanePriorityResolver.js",
    ],
  });

  const followup = runFollowupWorkerTask({
    previousState: {
      ...open,
      steps: ["locate", "patch"],
    },
    basename: "buildGraphSummary.js",
    files: [
      "repo/apps/demo-app-shadow/src/toolchain/buildGraphSummary.js",
      "repo/apps/demo-app/src/toolchain/buildGraphSummary.js",
    ],
  });

  assert.equal(open.projectRoot, "repo/apps/demo-app");
  assert.equal(open.ownedTarget, "repo/apps/demo-app/src/routing/lanePriorityResolver.js");
  assert.equal(followup.followupTarget, "repo/apps/demo-app/src/toolchain/buildGraphSummary.js");
  assert.deepEqual(followup.steps, ["locate", "patch", "followup", "verify"]);
  assert.deepEqual(followup.verificationCommands, [
    "npm test",
    "node scripts/verify-open-worker.js",
    "node scripts/verify-followup-worker.js",
  ]);
});

test("stays generic across alternate real app roots", () => {
  assert.equal(
    findProjectRoot(
      [
        "repo/apps/customer-portal-shadow/package.json",
        "repo/docs/customer-portal/package.json",
        "repo/legacy/customer-portal-copy/package.json",
        "repo/apps/customer-portal/package.json",
      ],
      "repo/apps/customer-portal/src/build"
    ),
    "repo/apps/customer-portal"
  );

  assert.equal(
    findOwnedTarget(
      [
        "repo/apps/customer-portal-shadow/src/toolchain/buildGraphSummary.js",
        "repo/apps/customer-portal/src/toolchain/buildGraphSummary.js",
      ],
      "buildGraphSummary.js"
    ),
    "repo/apps/customer-portal/src/toolchain/buildGraphSummary.js"
  );
});
`;

const expectedDocsFindProjectRoot = `function findProjectRoot() {
  return "DECOY_DOCS_FIND_PROJECT_ROOT";
}

module.exports = {
  findProjectRoot,
};
`;

const expectedLegacyFindOwnedTarget = `function findOwnedTarget() {
  return "DECOY_LEGACY_FIND_OWNED_TARGET";
}

module.exports = {
  findOwnedTarget,
};
`;

const expectedShadowSessionMerge = `function mergeRepairSession() {
  return {
    patchSummary: "DECOY_SHADOW_SESSION_MERGE",
  };
}

module.exports = {
  mergeRepairSession,
};
`;

function readRelative(relativePath) {
  return fs.readFileSync(path.join(__dirname, relativePath), "utf8");
}

try {
  const result = runOpenWorkerTask({
    basename: "lanePriorityResolver.js",
    startDir: "repo/apps/demo-app/src/build",
    manifestFiles: [
      "repo/apps/demo-app-shadow/package.json",
      "repo/docs/demo-app/package.json",
      "repo/legacy/demo-app-copy/package.json",
      "repo/apps/demo-app/package.json",
    ],
    files: [
      "repo/docs/notes/lanePriorityResolver.js",
      "repo/legacy/lanePriorityResolver.js",
      "repo/apps/demo-app/src/routing/lanePriorityResolver.js",
    ],
  });

  const alternate = runOpenWorkerTask({
    basename: "lanePriorityResolver.js",
    startDir: "repo/apps/customer-portal/src/build",
    manifestFiles: [
      "repo/apps/customer-portal-shadow/package.json",
      "repo/docs/customer-portal/package.json",
      "repo/legacy/customer-portal-copy/package.json",
      "repo/apps/customer-portal/package.json",
    ],
    files: [
      "repo/docs/notes/lanePriorityResolver.js",
      "repo/legacy/lanePriorityResolver.js",
      "repo/apps/customer-portal/src/routing/lanePriorityResolver.js",
    ],
  });

  assert.equal(result.projectRoot, "repo/apps/demo-app");
  assert.equal(result.ownedTarget, "repo/apps/demo-app/src/routing/lanePriorityResolver.js");
  assert.equal(alternate.projectRoot, "repo/apps/customer-portal");
  assert.equal(alternate.ownedTarget, "repo/apps/customer-portal/src/routing/lanePriorityResolver.js");
  assert.deepEqual(result.verificationCommands, [
    "npm test",
    "node scripts/verify-open-worker.js",
    "node scripts/verify-followup-worker.js",
  ]);

  assert.equal(readRelative("../src/runOpenWorkerTask.js"), expectedRunOpenWorkerTask);
  assert.equal(readRelative("../src/runFollowupWorkerTask.js"), expectedRunFollowupWorkerTask);
  assert.equal(readRelative("../test/runWorkerOwnershipTask.test.js"), expectedTestFile);
  assert.equal(readRelative("../../../docs/notes/findProjectRoot.js"), expectedDocsFindProjectRoot);
  assert.equal(readRelative("../../../legacy/findOwnedTarget.js"), expectedLegacyFindOwnedTarget);
  assert.equal(readRelative("../../demo-app-shadow/src/session/mergeRepairSession.js"), expectedShadowSessionMerge);

  console.log("VERIFY_OPEN_WORKER_OK");
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
