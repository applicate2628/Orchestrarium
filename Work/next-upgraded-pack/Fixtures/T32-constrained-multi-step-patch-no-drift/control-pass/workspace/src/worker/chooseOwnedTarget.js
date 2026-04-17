function chooseOwnedTarget({ ownerScope, candidates, basename }) {
  const inScope = candidates.filter((candidate) => candidate.startsWith(`${ownerScope}/`) && candidate.endsWith(`/${basename}`));
  return inScope[0] ?? null;
}

module.exports = {
  chooseOwnedTarget,
};
