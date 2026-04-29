const test = require("node:test");
const assert = require("node:assert/strict");

const { findInitialWorkspaceRoot } = require("../src/workspace/findInitialWorkspaceRoot");
const { recallWorkspaceRootAfterEdit } = require("../src/workspace/recallWorkspaceRootAfterEdit");
const { runPathRecallTask } = require("../src/runPathRecallTask");

const primaryManifestFiles = [
  "docs/project-mirror/package.json",
  "legacy/project-copy/package.json",
  "workspace/package.json",
];

test("discovers the real workspace root on the initial step", () => {
  assert.equal(findInitialWorkspaceRoot(primaryManifestFiles, "workspace/src/routing"), "workspace");
});

test("reuses the earlier correct root during a neutral follow-up step", () => {
  assert.equal(
    recallWorkspaceRootAfterEdit({
      previousRoot: "workspace",
      manifestFiles: primaryManifestFiles,
      currentStartDir: "notes\\handoff",
      priorEditPaths: [
        "workspace/src/ui/renderLaneCard.js",
        "docs/project-mirror/src/workspace/recallWorkspaceRootAfterEdit.js",
      ],
    }),
    "workspace"
  );
});

test("normalizes the accepted previous root before checking validity", () => {
  assert.equal(
    recallWorkspaceRootAfterEdit({
      previousRoot: "workspace\\",
      manifestFiles: primaryManifestFiles,
      currentStartDir: "notes\\handoff",
      priorEditPaths: [
        "docs/project-mirror/src/workspace/recallWorkspaceRootAfterEdit.js",
      ],
    }),
    "workspace"
  );
});

test("keeps the follow-up target under the earlier real workspace after distractor edits", () => {
  const plan = runPathRecallTask({
    manifestFiles: primaryManifestFiles,
    firstStartDir: "workspace/src/routing",
    secondStartDir: "notes/handoff",
    priorEditPaths: [
      "workspace/src/ui/renderLaneCard.js",
      "legacy/project-copy/src/ui/renderLaneCard.js",
      "docs/project-mirror/src/workspace/recallWorkspaceRootAfterEdit.js",
    ],
    requestedBasename: "buildContinuationPlan.js",
  });

  assert.equal(plan.initialRoot, "workspace");
  assert.equal(plan.recalledRoot, "workspace");
  assert.equal(plan.followUpTarget, "workspace/src/workspace/buildContinuationPlan.js");
});

test("uses the current concrete root when the previous root disappeared", () => {
  assert.equal(
    recallWorkspaceRootAfterEdit({
      previousRoot: "workspace",
      manifestFiles: [
        "docs/project-mirror/package.json",
        "packages/editor-app/package.json",
      ],
      currentStartDir: "packages/editor-app/src/routing",
      priorEditPaths: [
        "docs/project-mirror/src/workspace/recallWorkspaceRootAfterEdit.js",
      ],
    }),
    "packages/editor-app"
  );
});

test("uses prior edit evidence only after previous and current roots are unavailable", () => {
  assert.equal(
    recallWorkspaceRootAfterEdit({
      previousRoot: "workspace",
      manifestFiles: [
        "docs/project-mirror/package.json",
        "legacy/project-copy/package.json",
        "packages/editor-app/package.json",
      ],
      currentStartDir: "notes/follow-up",
      priorEditPaths: [
        "docs/project-mirror/src/ui/renderLaneCard.js",
        "packages/editor-app/src/ui/renderLaneCard.js",
      ],
    }),
    "packages/editor-app"
  );
});

test("stays generic across alternate real root names", () => {
  assert.equal(
    recallWorkspaceRootAfterEdit({
      previousRoot: "packages/editor-app",
      manifestFiles: [
        "docs/project-mirror/package.json",
        "legacy/project-copy/package.json",
        "packages/editor-app/package.json",
      ],
      currentStartDir: "notes/follow-up",
      priorEditPaths: [
        "packages/editor-app/src/ui/renderLaneCard.js",
        "docs/project-mirror/src/ui/renderLaneCard.js",
      ],
    }),
    "packages/editor-app"
  );
});

test("returns null when there is no viable continuity signal", () => {
  assert.equal(
    recallWorkspaceRootAfterEdit({
      previousRoot: null,
      manifestFiles: ["docs/project-mirror/package.json"],
      currentStartDir: "notes/handoff",
      priorEditPaths: ["notes/summary.md"],
    }),
    null
  );
});

test("returns null when only mirror roots are available", () => {
  assert.equal(
    recallWorkspaceRootAfterEdit({
      previousRoot: null,
      manifestFiles: [
        "docs/project-mirror/package.json",
        "legacy/project-copy/package.json",
      ],
      currentStartDir: "notes/handoff",
      priorEditPaths: [
        "docs/project-mirror/src/ui/renderLaneCard.js",
        "legacy/project-copy/src/ui/renderLaneCard.js",
      ],
    }),
    null
  );
});
