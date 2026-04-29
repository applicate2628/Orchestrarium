const test = require("node:test");
const assert = require("node:assert/strict");

const { findOwnedTarget } = require("../src/path/findOwnedTarget");
const { findWorkspaceRoot } = require("../src/workspace/findWorkspaceRoot");
const { runContinuityWorkerTask } = require("../src/runContinuityWorkerTask");

test("prefers the src owner over docs, scripts, and legacy decoys", () => {
  const files = [
    "docs/notes/lanePriorityResolver.js",
    "legacy/lanePriorityResolver.js",
    "scripts/lanePriorityResolver.js",
    "workspace/vendor/routing/lanePriorityResolver.js",
    "workspace/src/routing/lanePriorityResolver.js",
  ];

  assert.equal(findOwnedTarget(files, "lanePriorityResolver.js"), "workspace/src/routing/lanePriorityResolver.js");
});

test("stays generic across a second basename instead of hardcoding one path", () => {
  const files = [
    "legacy/buildGraphSummary.js",
    "workspace/vendor/toolchain/buildGraphSummary.js",
    "workspace/src/toolchain/buildGraphSummary.js",
    "scripts/buildGraphSummary.js",
    "docs/notes/buildGraphSummary.js",
  ];

  assert.equal(findOwnedTarget(files, "buildGraphSummary.js"), "workspace/src/toolchain/buildGraphSummary.js");
});

test("ignores src-shaped decoys that are outside the real owner tree", () => {
  const files = [
    "docs/src/routing/lanePriorityResolver.js",
    "workspace/test/fixtures/src/routing/lanePriorityResolver.js",
    "workspace/.generated/src/routing/lanePriorityResolver.js",
    "apps/control-panel/src/routing/lanePriorityResolver.js",
  ];

  assert.equal(findOwnedTarget(files, "lanePriorityResolver.js"), "apps/control-panel/src/routing/lanePriorityResolver.js");
});

test("returns null when the basename is absent instead of guessing a decoy", () => {
  assert.equal(findOwnedTarget(["workspace/src/routing/otherResolver.js"], "lanePriorityResolver.js"), null);
});

test("finds the real workspace root instead of docs or legacy mirrors", () => {
  const manifestFiles = [
    "docs/project-mirror/package.json",
    "legacy/project-copy/package.json",
    "workspace-shadow/package.json",
    "workspace/package.json",
  ];

  assert.equal(findWorkspaceRoot(manifestFiles, "workspace/src/toolchain"), "workspace");
});

test("chooses the deepest manifest root when roots overlap", () => {
  const manifestFiles = [
    "workspace/package.json",
    "workspace/packages/editor/package.json",
    "workspace/packages/editor-shadow/package.json",
  ];

  assert.equal(findWorkspaceRoot(manifestFiles, "workspace/packages/editor/src/routing"), "workspace/packages/editor");
});

test("matches roots by path boundary rather than raw prefix", () => {
  const manifestFiles = [
    "workspace/package.json",
    "workspace-old/package.json",
  ];

  assert.equal(findWorkspaceRoot(manifestFiles, "workspace-old/src/toolchain"), "workspace-old");
});

test("returns null instead of guessing when no manifest root owns the start directory", () => {
  const manifestFiles = [
    "docs/project-mirror/package.json",
    "legacy/project-copy/package.json",
  ];

  assert.equal(findWorkspaceRoot(manifestFiles, "notes/handoff"), null);
});

test("normalizes Windows separators before selecting the workspace root", () => {
  const manifestFiles = [
    "docs\\demo-app-mirror\\package.json",
    "legacy\\demo-app-copy\\package.json",
    "apps\\demo-app\\package.json",
  ];

  assert.equal(findWorkspaceRoot(manifestFiles, "apps\\demo-app\\src\\build"), "apps/demo-app");
});

test("assembles a coherent repair plan across both ownership helpers", () => {
  const plan = runContinuityWorkerTask({
    basename: "lanePriorityResolver.js",
    files: [
      "docs/notes/lanePriorityResolver.js",
      "legacy/lanePriorityResolver.js",
      "scripts/lanePriorityResolver.js",
      "workspace/vendor/routing/lanePriorityResolver.js",
      "workspace/src/routing/lanePriorityResolver.js",
    ],
    manifestFiles: [
      "docs/project-mirror/package.json",
      "legacy/project-copy/package.json",
      "workspace-shadow/package.json",
      "workspace/package.json",
    ],
    startDir: "workspace/src/toolchain",
  });

  assert.equal(plan.ownedTarget, "workspace/src/routing/lanePriorityResolver.js");
  assert.equal(plan.workspaceRoot, "workspace");
  assert.equal(
    plan.buildCommand,
    "node tools/run-build.js --root workspace --target workspace/src/routing/lanePriorityResolver.js"
  );
});

test("assembles a repair plan for a non-workspace root without hardcoded names", () => {
  const plan = runContinuityWorkerTask({
    basename: "lanePriorityResolver.js",
    files: [
      "docs/project-mirror/src/routing/lanePriorityResolver.js",
      "packages/editor-app/legacy/lanePriorityResolver.js",
      "packages/editor-app/src/routing/lanePriorityResolver.js",
    ],
    manifestFiles: [
      "docs/project-mirror/package.json",
      "packages/package.json",
      "packages/editor-app/package.json",
    ],
    startDir: "packages/editor-app/src/routing",
  });

  assert.equal(plan.ownedTarget, "packages/editor-app/src/routing/lanePriorityResolver.js");
  assert.equal(plan.workspaceRoot, "packages/editor-app");
  assert.equal(
    plan.buildCommand,
    "node tools/run-build.js --root packages/editor-app --target packages/editor-app/src/routing/lanePriorityResolver.js"
  );
});
