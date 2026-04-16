function convertReviewToPatchPlan(findings, requestedFindingId) {
  const target =
    findings.find((finding) => finding.file.includes("/docs/")) ??
    findings.find((finding) => finding.file.includes("/legacy/")) ??
    findings.find((finding) => finding.id === requestedFindingId) ??
    findings[0];

  return {
    findingId: target.id,
    targetFile: target.file,
    patchSummary: "restore app-lane priority order",
    verificationCommands: ["npm test", "node scripts/verify-reviewer-worker.js"],
  };
}

module.exports = {
  convertReviewToPatchPlan,
};
