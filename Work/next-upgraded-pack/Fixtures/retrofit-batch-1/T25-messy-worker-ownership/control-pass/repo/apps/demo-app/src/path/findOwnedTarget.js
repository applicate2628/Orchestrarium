function normalizePath(filePath) {
  return String(filePath ?? "").replace(/\\/g, "/");
}

function scoreCandidate(filePath) {
  const normalized = normalizePath(filePath);
  let score = 0;

  if (normalized.includes("/src/")) {
    score += 40;
  }

  if (normalized.includes("/apps/")) {
    score += 20;
  }

  for (const marker of ["shadow", "/docs/", "/legacy/", "copy", "mirror", "/notes/"]) {
    if (normalized.includes(marker)) {
      score -= 100;
    }
  }

  return score;
}

function findOwnedTarget(files, basename) {
  const matches = files
    .map(normalizePath)
    .filter((filePath) => filePath === basename || filePath.endsWith(`/${basename}`));

  if (matches.length === 0) {
    return null;
  }

  return [...matches].sort((left, right) => {
    const scoreDelta = scoreCandidate(right) - scoreCandidate(left);
    if (scoreDelta !== 0) {
      return scoreDelta;
    }

    return left.localeCompare(right);
  })[0];
}

module.exports = {
  findOwnedTarget,
};
