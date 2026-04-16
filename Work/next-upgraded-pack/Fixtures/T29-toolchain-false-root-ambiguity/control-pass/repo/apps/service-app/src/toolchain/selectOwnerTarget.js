function normalize(pathValue) {
  return pathValue.replace(/\\/g, "/");
}

function distanceScore(candidate, startDir) {
  if (startDir.startsWith(candidate.replace(/\/[^/]+$/, ""))) {
    return 0;
  }

  return Math.abs(candidate.length - startDir.length);
}

function selectOwnerTarget({ basename, files, workspaceRoot, startDir }) {
  const normalizedRoot = normalize(workspaceRoot);
  const normalizedStart = normalize(startDir);
  const matches = files
    .map(normalize)
    .filter((entry) => entry.endsWith(`/${basename}`));
  const ownedMatches = matches.filter((entry) => entry.startsWith(`${normalizedRoot}/`));

  return ownedMatches.sort((left, right) => distanceScore(left, normalizedStart) - distanceScore(right, normalizedStart))[0];
}

module.exports = {
  selectOwnerTarget,
};
