function appendPatchStep({ patchState, nextStep }) {
  return {
    ...patchState,
    steps: [nextStep],
  };
}

module.exports = {
  appendPatchStep,
};
