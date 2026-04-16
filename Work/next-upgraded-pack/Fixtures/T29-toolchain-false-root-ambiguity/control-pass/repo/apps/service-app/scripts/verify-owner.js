const assert = require("node:assert/strict");

const { runToolchainTask } = require("../src/runToolchainTask");

function verifyScenario({ manifestFiles, files, startDir, root, target, basename }) {
  const result = runToolchainTask({
    basename,
    files,
    manifestFiles,
    startDir,
  });

  assert.equal(result.workspaceRoot, root);
  assert.equal(result.ownedTarget, target);
  assert.equal(result.buildCommand, `node tools/run-build.js --root ${root} --target ${target}`);
}

try {
  verifyScenario({
    basename: "buildPlan.js",
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
    root: "repo/apps/service-app",
    target: "repo/apps/service-app/src/toolchain/buildPlan.js",
  });

  verifyScenario({
    basename: "lanePriorityResolver.js",
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
    root: "repo/apps/service-app",
    target: "repo/apps/service-app/src/routing/lanePriorityResolver.js",
  });

  verifyScenario({
    basename: "buildPlan.js",
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
    root: "sandbox/apps/ops-app",
    target: "sandbox/apps/ops-app/src/toolchain/buildPlan.js",
  });

  console.log("VERIFY_T29_OWNER_OK");
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
