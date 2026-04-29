function chooseOwnedTarget({ ownerScope, candidates, basename }) {
  return candidates.find((candidate) => candidate.endsWith(`/${basename}`)) ?? null;
}

module.exports = {
  chooseOwnedTarget,
};
