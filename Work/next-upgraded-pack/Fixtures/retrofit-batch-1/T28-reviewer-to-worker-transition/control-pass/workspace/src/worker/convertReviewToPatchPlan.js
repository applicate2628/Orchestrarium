function scoreFinding(finding) {
  let score = 0;

  if (finding.file.includes("/src/")) {
    score += 100;
  }

  if (finding.file.includes("/docs/")) {
    score -= 90;
  }

  if (finding.file.includes("/legacy/")) {
    score -= 90;
  }

  if (finding.file.startsWith("workspace-shadow/")) {
    score -= 120;
  }

  if (finding.severity === "high") {
    score += 20;
  }

  return score;
}

function convertReviewToPatchPlan(findings, requestedFindingId) {
  const exactMatch = requestedFindingId
    ? findings.find((finding) => finding.id === requestedFindingId)
    : null;

  const target =
    exactMatch ??
    [...findings].sort((left, right) => {
      const scoreDelta = scoreFinding(right) - scoreFinding(left);

      if (scoreDelta !== 0) {
        return scoreDelta;
      }

      return left.id.localeCompare(right.id);
    })[0];

  return {
    findingId: target.id,
    targetFile: target.file,
    patchSummary: target.summary,
    verificationCommands: ["npm test", "node scripts/verify-reviewer-worker.js"],
  };
}

module.exports = {
  convertReviewToPatchPlan,
};
