function normalizePath(filePath) {
  return filePath.replace(/\\/g, "/");
}

function scoreRoot(rootPath, appName) {
  let score = 0;

  if (rootPath.startsWith("repo/apps/")) {
    score += 50;
  }

  if (rootPath.endsWith(`/${appName}`)) {
    score += 25;
  }

  if (rootPath.includes("-shadow")) {
    score -= 80;
  }

  if (rootPath.includes("/docs/")) {
    score -= 60;
  }

  if (rootPath.includes("/legacy/")) {
    score -= 60;
  }

  if (rootPath.includes("-copy")) {
    score -= 40;
  }

  return score;
}

function findBuildRoot(files, appName) {
  const roots = files
    .map(normalizePath)
    .filter((filePath) => filePath.endsWith("/build.config.json") && filePath.includes(appName))
    .map((filePath) => filePath.slice(0, -"/build.config.json".length));

  if (roots.length === 0) {
    return null;
  }

  return [...roots].sort((left, right) => {
    const scoreDelta = scoreRoot(right, appName) - scoreRoot(left, appName);

    if (scoreDelta !== 0) {
      return scoreDelta;
    }

    return left.localeCompare(right);
  })[0];
}

module.exports = {
  findBuildRoot,
};
