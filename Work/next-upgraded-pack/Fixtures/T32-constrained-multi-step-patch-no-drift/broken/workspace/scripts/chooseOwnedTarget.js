function chooseOwnedTarget(candidates, basename) {
  return candidates.find((candidate) => candidate.endsWith(`/${basename}`)) ?? null;
}

module.exports = {
  chooseOwnedTarget,
};
