const { deriveFindings } = require("./review/deriveFindings");
const { convertReviewToPatchPlan } = require("./worker/convertReviewToPatchPlan");

function runReviewerWorkerFlow({ reviewSet = "main", requestedFindingId } = {}) {
  const findings = deriveFindings(reviewSet);
  const patchPlan = convertReviewToPatchPlan(findings, requestedFindingId);

  return {
    reviewSet,
    findings,
    patchPlan,
  };
}

module.exports = {
  runReviewerWorkerFlow,
};
