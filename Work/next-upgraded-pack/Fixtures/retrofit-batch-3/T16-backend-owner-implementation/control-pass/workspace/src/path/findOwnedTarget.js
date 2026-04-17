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

  return matches.find((filePath) => filePath === `src/${basename}` || filePath.includes("/src/") || filePath.startsWith("src/")) ?? matches[0];
}

module.exports = {
  findOwnedTarget,
};
