const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const { runToolchainOwnerTask } = require("../src/runToolchainOwnerTask");

const expectedRunToolchainOwnerTask = `const { findBuildRoot } = require("./toolchain/findBuildRoot");
const { collectBuildEntrypoints } = require("./toolchain/collectBuildEntrypoints");

function runToolchainOwnerTask({ files, appName }) {
  const buildRoot = findBuildRoot(files, appName);

  if (!buildRoot) {
    return null;
  }

  return {
    appName,
    ...collectBuildEntrypoints(buildRoot),
    verificationCommands: ["npm test", "node scripts/verify-toolchain-owner.js"],
  };
}

module.exports = {
  runToolchainOwnerTask,
};
`;

const expectedTestFile = `const test = require("node:test");
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
`;

const expectedDocsDecoy = `function findBuildRoot() {
  return "DECOY_DOCS_FIND_BUILD_ROOT";
}

module.exports = {
  findBuildRoot,
};
`;

const expectedLegacyDecoy = `function findBuildRoot() {
  return "DECOY_LEGACY_FIND_BUILD_ROOT";
}

module.exports = {
  findBuildRoot,
};
`;

const expectedShadowCollectEntrypoints = `function collectBuildEntrypoints() {
  return {
    ownerPath: "DECOY_SHADOW_COLLECT_BUILD_ENTRYPOINTS",
  };
}

module.exports = {
  collectBuildEntrypoints,
};
`;

function readRelative(relativePath) {
  return fs.readFileSync(path.join(__dirname, relativePath), "utf8");
}

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

try {
  const service = runToolchainOwnerTask({ files, appName: "service-app" });
  const worker = runToolchainOwnerTask({ files, appName: "worker-app" });

  assert.equal(service.buildRoot, "repo/apps/service-app");
  assert.equal(service.ownerPath, "repo/apps/service-app/src/toolchain/collectBuildEntrypoints.js");
  assert.equal(service.buildConfigPath, "repo/apps/service-app/build.config.json");
  assert.equal(worker.buildRoot, "repo/apps/worker-app");
  assert.equal(worker.ownerPath, "repo/apps/worker-app/src/toolchain/collectBuildEntrypoints.js");
  assert.equal(worker.buildConfigPath, "repo/apps/worker-app/build.config.json");
  assert.deepEqual(service.verificationCommands, ["npm test", "node scripts/verify-toolchain-owner.js"]);

  assert.equal(readRelative("../src/runToolchainOwnerTask.js"), expectedRunToolchainOwnerTask);
  assert.equal(readRelative("../test/runToolchainOwnerTask.test.js"), expectedTestFile);
  assert.equal(readRelative("../../../docs/notes/findBuildRoot.js"), expectedDocsDecoy);
  assert.equal(readRelative("../../../legacy/findBuildRoot.js"), expectedLegacyDecoy);
  assert.equal(readRelative("../../service-app-shadow/src/toolchain/collectBuildEntrypoints.js"), expectedShadowCollectEntrypoints);

  console.log("VERIFY_TOOLCHAIN_OWNER_OK");
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
