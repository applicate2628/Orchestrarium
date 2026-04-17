const { findOwnedTarget } = require("./path/findOwnedTarget");

function buildPatchPlan(files, basename) {
  const ownedTarget = findOwnedTarget(files, basename);

  if (!ownedTarget) {
    throw new Error(`No owned target found for ${basename}`);
  }

  return {
    ownedTarget,
    patchSurface: [ownedTarget],
  };
}

module.exports = {
  buildPatchPlan,
};
