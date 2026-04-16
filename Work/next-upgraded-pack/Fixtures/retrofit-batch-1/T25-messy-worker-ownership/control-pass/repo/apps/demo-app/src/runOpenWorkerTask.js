const { findProjectRoot } = require("./workspace/findProjectRoot");
const { findOwnedTarget } = require("./path/findOwnedTarget");

function runOpenWorkerTask({ basename, startDir, manifestFiles, files }) {
  const projectRoot = findProjectRoot(manifestFiles, startDir);
  const ownedTarget = findOwnedTarget(files, basename);

  return {
    projectRoot,
    ownedTarget,
    verificationCommands: [
      "npm test",
      "node scripts/verify-open-worker.js",
      "node scripts/verify-followup-worker.js",
    ],
    repairNotes: [`open repair scoped to ${projectRoot ?? "unknown-root"}`],
  };
}

module.exports = {
  runOpenWorkerTask,
};
