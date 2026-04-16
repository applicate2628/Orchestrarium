function normalizePath(filePath) {
  return String(filePath ?? "").replace(/\\/g, "/");
}

function findOwnedTarget(files, basename) {
  const matches = files
    .map(normalizePath)
    .filter((filePath) => filePath === basename || filePath.endsWith(`/${basename}`));

  if (matches.length === 0) {
    return null;
  }

  return matches.find((filePath) => filePath.includes("shadow")) ?? matches[0];
}

module.exports = {
  findOwnedTarget,
};
