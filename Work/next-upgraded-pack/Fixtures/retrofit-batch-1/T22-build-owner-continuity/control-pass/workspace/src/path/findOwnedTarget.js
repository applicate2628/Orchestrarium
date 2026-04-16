function normalizePath(filePath) {
  return filePath.replace(/\\/g, "/");
}

function findOwnedTarget(files, basename) {
  const matches = files
    .map(normalizePath)
    .filter((filePath) => filePath === basename || filePath.endsWith(`/${basename}`));

  if (matches.length === 0) {
    return null;
  }

  const srcMatches = matches.filter((filePath) => filePath.includes("/src/"));

  if (srcMatches.length > 0) {
    return srcMatches.sort((left, right) => left.length - right.length)[0];
  }

  return matches.sort((left, right) => left.length - right.length)[0];
}

module.exports = {
  findOwnedTarget,
};
