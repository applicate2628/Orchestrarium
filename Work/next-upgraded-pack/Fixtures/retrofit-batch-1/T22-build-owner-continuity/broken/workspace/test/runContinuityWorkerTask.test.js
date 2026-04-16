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

test("finds the real workspace root instead of docs or legacy mirrors", () => {
  const manifestFiles = [
    "docs/project-mirror/package.json",
    "legacy/project-copy/package.json",
    "workspace-shadow/package.json",
    "workspace/package.json",
  ];

  assert.equal(findWorkspaceRoot(manifestFiles, "workspace/src/toolchain"), "workspace");
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
