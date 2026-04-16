function appendWorkerStep(session, step) {
  return {
    ...session,
    steps: [...(session.steps ?? []), step],
  };
}

module.exports = {
  appendWorkerStep,
};
