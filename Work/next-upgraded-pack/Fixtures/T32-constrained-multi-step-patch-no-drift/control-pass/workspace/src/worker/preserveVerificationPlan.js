function preserveVerificationPlan({ patchState, newSummary }) {
  return {
    ...patchState,
    patchSummary: newSummary,
    verificationCommands: patchState.verificationCommands,
  };
}

module.exports = {
  preserveVerificationPlan,
};
