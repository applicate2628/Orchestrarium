function carryForwardWorkerState(session, patchSummary) {
  return {
    patchSummary,
    steps: session.steps,
  };
}

module.exports = {
  carryForwardWorkerState,
};
