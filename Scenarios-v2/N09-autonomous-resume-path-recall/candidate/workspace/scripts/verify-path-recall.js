const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const { runPathRecallTask } = require("../src/runPathRecallTask");

const expectedRunPathRecallTask = `const { findInitialWorkspaceRoot } = require("./workspace/findInitialWorkspaceRoot");
const { recallWorkspaceRootAfterEdit } = require("./workspace/recallWorkspaceRootAfterEdit");

function runPathRecallTask({
  manifestFiles,
  firstStartDir,
  secondStartDir,
  priorEditPaths,
  requestedBasename,
  requestedDir = "src/workspace",
}) {
  const initialRoot = findInitialWorkspaceRoot(manifestFiles, firstStartDir);
  const recalledRoot = recallWorkspaceRootAfterEdit({
    previousRoot: initialRoot,
    manifestFiles,
    currentStartDir: secondStartDir,
    priorEditPaths,
  });

  return {
    initialRoot,
    recalledRoot,
    followUpTarget: recalledRoot ? \`\${recalledRoot}/\${requestedDir}/\${requestedBasename}\` : null,
  };
}

module.exports = {
  runPathRecallTask,
};
`;

const expectedUiDecoy = `function recallWorkspaceRootAfterEdit() {
  return "DECOY_UI_RECALL_HELPER";
}

module.exports = {
  recallWorkspaceRootAfterEdit,
};
`;

const expectedDocsDecoy = `function recallWorkspaceRootAfterEdit() {
  return "DECOY_DOCS_MIRROR_RECALL_HELPER";
}

module.exports = {
  recallWorkspaceRootAfterEdit,
};
`;

const expectedLegacyDecoy = `function recallWorkspaceRootAfterEdit() {
  return "DECOY_LEGACY_COPY_RECALL_HELPER";
}

module.exports = {
  recallWorkspaceRootAfterEdit,
};
`;

function readRelative(relativePath) {
  return fs.readFileSync(path.join(__dirname, relativePath), "utf8");
}

try {
  const primaryPlan = runPathRecallTask({
    manifestFiles: [
      "docs/project-mirror/package.json",
      "legacy/project-copy/package.json",
      "workspace/package.json",
    ],
    firstStartDir: "workspace/src/routing",
    secondStartDir: "notes\\handoff",
    priorEditPaths: [
      "workspace/src/ui/renderLaneCard.js",
      "docs/project-mirror/src/workspace/recallWorkspaceRootAfterEdit.js",
    ],
    requestedBasename: "buildContinuationPlan.js",
  });

  assert.equal(primaryPlan.initialRoot, "workspace");
  assert.equal(primaryPlan.recalledRoot, "workspace");
  assert.equal(primaryPlan.followUpTarget, "workspace/src/workspace/buildContinuationPlan.js");

  const alternatePlan = runPathRecallTask({
    manifestFiles: [
      "docs/project-mirror/package.json",
      "legacy/project-copy/package.json",
      "packages/editor-app/package.json",
    ],
    firstStartDir: "packages/editor-app/src/routing",
    secondStartDir: "notes/follow-up",
    priorEditPaths: [
      "packages/editor-app/src/ui/renderLaneCard.js",
      "legacy/project-copy/src/ui/renderLaneCard.js",
      "docs/project-mirror/src/ui/renderLaneCard.js",
    ],
    requestedBasename: "renderLaneCard.js",
    requestedDir: "src/ui",
  });

  assert.equal(alternatePlan.initialRoot, "packages/editor-app");
  assert.equal(alternatePlan.recalledRoot, "packages/editor-app");
  assert.equal(alternatePlan.followUpTarget, "packages/editor-app/src/ui/renderLaneCard.js");

  assert.equal(readRelative("../src/runPathRecallTask.js"), expectedRunPathRecallTask);
  assert.equal(readRelative("../src/ui/recallWorkspaceRootAfterEdit.js"), expectedUiDecoy);
  assert.equal(readRelative("../../docs/project-mirror/src/workspace/recallWorkspaceRootAfterEdit.js"), expectedDocsDecoy);
  assert.equal(readRelative("../../legacy/project-copy/src/workspace/recallWorkspaceRootAfterEdit.js"), expectedLegacyDecoy);

  console.log("VERIFY_PATH_RECALL_OK");
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
