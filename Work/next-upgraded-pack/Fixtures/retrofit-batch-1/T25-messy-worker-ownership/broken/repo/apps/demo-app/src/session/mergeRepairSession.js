function mergeRepairSession(previousState, update) {
  return {
    ...update,
    steps: update.steps ?? [],
  };
}

module.exports = {
  mergeRepairSession,
};
