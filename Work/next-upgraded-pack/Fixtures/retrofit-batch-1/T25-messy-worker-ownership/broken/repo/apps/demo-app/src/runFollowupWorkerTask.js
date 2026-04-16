const { findOwnedTarget } = require("./path/findOwnedTarget");
const { mergeRepairSession } = require("./session/mergeRepairSession");

function runFollowupWorkerTask({ previousState, basename, files }) {
  const followupTarget = findOwnedTarget(files, basename);

  return mergeRepairSession(previousState, {
    followupTarget,
    steps: ["followup", "verify"],
    repairNotes: [`followup validated ${basename}`],
  });
}

module.exports = {
  runFollowupWorkerTask,
};
