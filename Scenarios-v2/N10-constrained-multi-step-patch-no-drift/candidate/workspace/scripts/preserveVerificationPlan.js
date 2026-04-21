function preserveVerificationPlan(state, summary) {
  return {
    ...state,
    patchSummary: summary,
    verificationCommands: ["npm test"],
  };
}

module.exports = {
  preserveVerificationPlan,
};
