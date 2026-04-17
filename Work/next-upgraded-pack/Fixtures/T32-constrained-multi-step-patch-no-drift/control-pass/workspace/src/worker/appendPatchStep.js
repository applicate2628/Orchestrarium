function appendPatchStep({ patchState, nextStep }) {
  return {
    ...patchState,
    steps: [...patchState.steps, nextStep],
  };
}

module.exports = {
  appendPatchStep,
};
