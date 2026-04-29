const { chooseOwnedTarget } = require("./worker/chooseOwnedTarget");
const { appendPatchStep } = require("./worker/appendPatchStep");
const { preserveVerificationPlan } = require("./worker/preserveVerificationPlan");

function runPatchFlow({ ownerScope, basename, candidates, patchState, nextStep, newSummary }) {
  const ownedTarget = chooseOwnedTarget({ ownerScope, basename, candidates });
  const withStep = appendPatchStep({ patchState: { ...patchState, ownedTarget }, nextStep });
  return preserveVerificationPlan({ patchState: withStep, newSummary });
}

module.exports = {
  runPatchFlow,
};
