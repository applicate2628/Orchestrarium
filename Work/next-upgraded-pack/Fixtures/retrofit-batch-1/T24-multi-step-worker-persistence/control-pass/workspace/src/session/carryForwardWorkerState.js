function carryForwardWorkerState(session, patchSummary) {
  return {
    ...session,
    patchSummary,
  };
}

module.exports = {
  carryForwardWorkerState,
};
