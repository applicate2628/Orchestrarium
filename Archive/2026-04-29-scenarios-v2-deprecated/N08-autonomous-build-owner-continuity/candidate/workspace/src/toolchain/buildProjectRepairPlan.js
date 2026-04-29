const { findOwnedTarget } = require("../path/findOwnedTarget");
const { findWorkspaceRoot } = require("../workspace/findWorkspaceRoot");

function buildProjectRepairPlan({ basename, files, manifestFiles, startDir }) {
  const ownedTarget = findOwnedTarget(files, basename);
  const workspaceRoot = findWorkspaceRoot(manifestFiles, startDir);

  return {
    ownedTarget,
    workspaceRoot,
    buildCommand:
      ownedTarget && workspaceRoot
        ? `node tools/run-build.js --root ${workspaceRoot} --target ${ownedTarget}`
        : null,
  };
}

module.exports = {
  buildProjectRepairPlan,
};
