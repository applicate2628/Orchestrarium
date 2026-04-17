function preserveVerificationPlan({ patchState, newSummary }) {
  return {
    ...patchState,
    patchSummary: newSummary,
    verificationCommands: ["npm test"],
  };
}

module.exports = {
  preserveVerificationPlan,
};
