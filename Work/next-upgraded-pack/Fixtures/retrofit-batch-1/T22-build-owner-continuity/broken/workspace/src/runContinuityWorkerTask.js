const { buildProjectRepairPlan } = require("./toolchain/buildProjectRepairPlan");

function runContinuityWorkerTask({ basename, files, manifestFiles, startDir }) {
  return buildProjectRepairPlan({
    basename,
    files,
    manifestFiles,
    startDir,
  });
}

module.exports = {
  runContinuityWorkerTask,
};
