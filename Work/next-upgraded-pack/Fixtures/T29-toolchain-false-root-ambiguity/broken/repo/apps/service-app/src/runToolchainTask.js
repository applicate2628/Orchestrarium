const { findWorkspaceRoot } = require("./toolchain/findWorkspaceRoot");
const { selectOwnerTarget } = require("./toolchain/selectOwnerTarget");

function buildCommandFor(workspaceRoot, ownedTarget) {
  return `node tools/run-build.js --root ${workspaceRoot} --target ${ownedTarget}`;
}

function runToolchainTask({ basename, files, manifestFiles, startDir }) {
  const workspaceRoot = findWorkspaceRoot({ manifestFiles, startDir });
  const ownedTarget = selectOwnerTarget({ basename, files, workspaceRoot, startDir });

  return {
    workspaceRoot,
    ownedTarget,
    buildCommand: buildCommandFor(workspaceRoot, ownedTarget),
  };
}

module.exports = {
  runToolchainTask,
};
