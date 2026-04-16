const test = require("node:test");
const assert = require("node:assert/strict");

const { findBuildRoot } = require("../src/toolchain/findBuildRoot");
const { runToolchainOwnerTask } = require("../src/runToolchainOwnerTask");

const files = [
  "repo/apps/service-app-shadow/build.config.json",
  "repo/docs/service-app/build.config.json",
  "repo/legacy/service-app-copy/build.config.json",
  "repo/apps/service-app/build.config.json",
  "repo/apps/worker-app-shadow/build.config.json",
  "repo/docs/worker-app/build.config.json",
  "repo/legacy/worker-app-copy/build.config.json",
  "repo/apps/worker-app/build.config.json",
];

test("prefers the real service app root over shadow and mirror roots", () => {
  assert.equal(findBuildRoot(files, "service-app"), "repo/apps/service-app");
});

test("stays generic across more than one app basename", () => {
  assert.equal(findBuildRoot(files, "worker-app"), "repo/apps/worker-app");
});

test("returns the real owner file and build config for each real app root", () => {
  const service = runToolchainOwnerTask({ files, appName: "service-app" });
  const worker = runToolchainOwnerTask({ files, appName: "worker-app" });

  assert.equal(service.buildRoot, "repo/apps/service-app");
  assert.equal(service.ownerPath, "repo/apps/service-app/src/toolchain/collectBuildEntrypoints.js");
  assert.equal(service.buildConfigPath, "repo/apps/service-app/build.config.json");

  assert.equal(worker.buildRoot, "repo/apps/worker-app");
  assert.equal(worker.ownerPath, "repo/apps/worker-app/src/toolchain/collectBuildEntrypoints.js");
  assert.equal(worker.buildConfigPath, "repo/apps/worker-app/build.config.json");
});
