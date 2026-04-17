function selectAdmittedSignal({ candidates }) {
  const admitted = candidates.filter((candidate) => candidate.status === "PASS" && candidate.verifierPassed);
  if (admitted.length === 0) {
    return null;
  }

  admitted.sort((left, right) => {
    if (right.evidenceWeight !== left.evidenceWeight) {
      return right.evidenceWeight - left.evidenceWeight;
    }

    return left.overlayLevel.localeCompare(right.overlayLevel);
  });

  return admitted[0];
}

module.exports = {
  selectAdmittedSignal,
};
