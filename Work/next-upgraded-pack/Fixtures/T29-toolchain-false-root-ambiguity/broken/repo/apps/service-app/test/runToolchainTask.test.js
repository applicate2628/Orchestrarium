const test = require("node:test");
const assert = require("node:assert/strict");

const { runToolchainTask } = require("../src/runToolchainTask");

function baseScenario() {
  return {
    manifestFiles: [
      "repo/apps/docs-app/package.json",
      "repo/apps/service-app/package.json",
      "repo/tooling-shadow/package.json",
    ],
    files: [
      "repo/apps/docs-app/src/toolchain/buildPlan.js",
      "repo/apps/service-app/src/toolchain/buildPlan.js",
      "repo/tooling-shadow/src/toolchain/buildPlan.js",
      "repo/apps/docs-app/src/routing/lanePriorityResolver.js",
      "repo/apps/service-app/src/routing/lanePriorityResolver.js",
      "repo/tooling-shadow/src/routing/lanePriorityResolver.js",
    ],
    startDir: "repo/apps/service-app/src/toolchain",
  };
}

function alternateScenario() {
  return {
    manifestFiles: [
      "sandbox/apps/docs-app/package.json",
      "sandbox/apps/ops-app/package.json",
      "sandbox/tooling-shadow/package.json",
    ],
    files: [
      "sandbox/apps/docs-app/src/toolchain/buildPlan.js",
      "sandbox/apps/ops-app/src/toolchain/buildPlan.js",
      "sandbox/tooling-shadow/src/toolchain/buildPlan.js",
      "sandbox/apps/docs-app/src/routing/lanePriorityResolver.js",
      "sandbox/apps/ops-app/src/routing/lanePriorityResolver.js",
      "sandbox/tooling-shadow/src/routing/lanePriorityResolver.js",
    ],
    startDir: "sandbox/apps/ops-app/src/toolchain",
  };
}

test("chooses the real owner root for toolchain tasks", () => {
  const scenario = baseScenario();
  const result = runToolchainTask({
    basename: "buildPlan.js",
    files: scenario.files,
    manifestFiles: scenario.manifestFiles,
    startDir: scenario.startDir,
  });

  assert.equal(result.workspaceRoot, "repo/apps/service-app");
  assert.equal(result.ownedTarget, "repo/apps/service-app/src/toolchain/buildPlan.js");
  assert.equal(
    result.buildCommand,
    "node tools/run-build.js --root repo/apps/service-app --target repo/apps/service-app/src/toolchain/buildPlan.js"
  );
});

test("chooses the real owner file for routing helpers too", () => {
  const scenario = baseScenario();
  const result = runToolchainTask({
    basename: "lanePriorityResolver.js",
    files: scenario.files,
    manifestFiles: scenario.manifestFiles,
    startDir: scenario.startDir,
  });

  assert.equal(result.workspaceRoot, "repo/apps/service-app");
  assert.equal(result.ownedTarget, "repo/apps/service-app/src/routing/lanePriorityResolver.js");
});

test("rejects brittle hardcoding of the service-app path", () => {
  const scenario = alternateScenario();
  const result = runToolchainTask({
    basename: "buildPlan.js",
    files: scenario.files,
    manifestFiles: scenario.manifestFiles,
    startDir: scenario.startDir,
  });

  assert.equal(result.workspaceRoot, "sandbox/apps/ops-app");
  assert.equal(result.ownedTarget, "sandbox/apps/ops-app/src/toolchain/buildPlan.js");
});
