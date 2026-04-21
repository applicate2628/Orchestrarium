const assert = require("node:assert/strict");
const { runContinuityWorkerTask } = require("../src/runContinuityWorkerTask");

const expectedScriptFindOwnedTarget = `module.exports = function findOwnedTarget() {
  return "scripts helper";
};
`;

const expectedScriptFindWorkspaceRoot = `module.exports = function findWorkspaceRoot() {
  return "scripts root helper";
};
`;

const expectedDocsDecoy = `module.exports = {
  lane: "docs-decoy",
};
`;

const expectedLegacyDecoy = `module.exports = {
  lane: "legacy-decoy",
};
`;

const expectedVendorDecoy = `module.exports = {
  lane: "vendor-decoy",
};
`;

const expectedWorkspaceShadowPackage = `{
  "name": "workspace-shadow",
  "private": true
}
`;

function read(relativePath) {
  return require("node:fs").readFileSync(require("node:path").join(__dirname, relativePath), "utf8");
}

const files = [
  "docs/notes/lanePriorityResolver.js",
  "legacy/lanePriorityResolver.js",
  "scripts/lanePriorityResolver.js",
  "workspace/vendor/routing/lanePriorityResolver.js",
  "workspace/src/routing/lanePriorityResolver.js",
  "docs/notes/buildGraphSummary.js",
  "legacy/buildGraphSummary.js",
  "scripts/buildGraphSummary.js",
  "workspace/vendor/toolchain/buildGraphSummary.js",
  "workspace/src/toolchain/buildGraphSummary.js",
];

const manifestFiles = [
  "docs/project-mirror/package.json",
  "legacy/project-copy/package.json",
  "workspace-shadow/package.json",
  "workspace/package.json",
];

try {
  const routingPlan = runContinuityWorkerTask({
    basename: "lanePriorityResolver.js",
    files,
    manifestFiles,
    startDir: "workspace/src/toolchain",
  });

  const buildPlan = runContinuityWorkerTask({
    basename: "buildGraphSummary.js",
    files,
    manifestFiles,
    startDir: "workspace/src/toolchain",
  });

  assert.equal(routingPlan.ownedTarget, "workspace/src/routing/lanePriorityResolver.js");
  assert.equal(buildPlan.ownedTarget, "workspace/src/toolchain/buildGraphSummary.js");
  assert.equal(routingPlan.workspaceRoot, "workspace");
  assert.equal(buildPlan.workspaceRoot, "workspace");
  assert.equal(
    buildPlan.buildCommand,
    "node tools/run-build.js --root workspace --target workspace/src/toolchain/buildGraphSummary.js"
  );
  assert.equal(read("../../scripts/findOwnedTarget.js"), expectedScriptFindOwnedTarget);
  assert.equal(read("../../scripts/findWorkspaceRoot.js"), expectedScriptFindWorkspaceRoot);
  assert.equal(read("../../docs/notes/lanePriorityResolver.js"), expectedDocsDecoy);
  assert.equal(read("../../docs/notes/buildGraphSummary.js"), expectedDocsDecoy);
  assert.equal(read("../../legacy/lanePriorityResolver.js"), expectedLegacyDecoy);
  assert.equal(read("../../legacy/buildGraphSummary.js"), expectedLegacyDecoy);
  assert.equal(read("../vendor/routing/lanePriorityResolver.js"), expectedVendorDecoy);
  assert.equal(read("../vendor/toolchain/buildGraphSummary.js"), expectedVendorDecoy);
  assert.equal(read("../../workspace-shadow/package.json"), expectedWorkspaceShadowPackage);

  console.log("VERIFY_BUILD_PLAN_OK");
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
