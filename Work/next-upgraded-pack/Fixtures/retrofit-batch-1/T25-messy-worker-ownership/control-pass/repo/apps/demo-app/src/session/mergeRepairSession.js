function mergeRepairSession(previousState, update) {
  return {
    ...previousState,
    ...update,
    steps: [...(previousState.steps ?? []), ...(update.steps ?? [])],
    repairNotes: [...(previousState.repairNotes ?? []), ...(update.repairNotes ?? [])],
    verificationCommands: update.verificationCommands ?? previousState.verificationCommands ?? [],
  };
}

module.exports = {
  mergeRepairSession,
};
