function normalizePath(filePath) {
  return filePath.replace(/\\/g, "/");
}

function scorePath(filePath, ownerScope) {
  let score = 0;

  if (ownerScope && filePath.startsWith(`${ownerScope}/`)) {
    score += 80;
  }

  if (filePath.includes("/src/")) {
    score += 20;
  }

  if (filePath.startsWith("workspace-shadow/")) {
    score -= 80;
  }

  if (filePath.includes("/docs/")) {
    score -= 60;
  }

  if (filePath.includes("/legacy/")) {
    score -= 60;
  }

  return score;
}

function resolveFollowupTarget(session, basename) {
  const ownerScope = session.ownerScope ? normalizePath(session.ownerScope) : null;
  const files = session.availableFiles
    .map(normalizePath)
    .filter((filePath) => filePath.endsWith(`/${basename}`));

  if (files.length === 0) {
    return null;
  }

  return [...files].sort((left, right) => {
    const scoreDelta = scorePath(right, ownerScope) - scorePath(left, ownerScope);

    if (scoreDelta !== 0) {
      return scoreDelta;
    }

    return left.localeCompare(right);
  })[0];
}

module.exports = {
  resolveFollowupTarget,
};
