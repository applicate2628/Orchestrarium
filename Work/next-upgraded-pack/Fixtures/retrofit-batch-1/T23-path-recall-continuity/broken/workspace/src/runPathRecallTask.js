const { findInitialWorkspaceRoot } = require("./workspace/findInitialWorkspaceRoot");
const { recallWorkspaceRootAfterEdit } = require("./workspace/recallWorkspaceRootAfterEdit");

function runPathRecallTask({
  manifestFiles,
  firstStartDir,
  secondStartDir,
  priorEditPaths,
  requestedBasename,
  requestedDir = "src/workspace",
}) {
  const initialRoot = findInitialWorkspaceRoot(manifestFiles, firstStartDir);
  const recalledRoot = recallWorkspaceRootAfterEdit({
    previousRoot: initialRoot,
    manifestFiles,
    currentStartDir: secondStartDir,
    priorEditPaths,
  });

  return {
    initialRoot,
    recalledRoot,
    followUpTarget: recalledRoot ? `${recalledRoot}/${requestedDir}/${requestedBasename}` : null,
  };
}

module.exports = {
  runPathRecallTask,
};
