function normalizePath(filePath) {
  return filePath.replace(/\\/g, "/").replace(/\/+$/g, "");
}

function toRoot(manifestPath) {
  const normalized = normalizePath(manifestPath);

  return normalized.endsWith("/package.json")
    ? normalized.slice(0, -"package.json".length - 1)
    : normalized;
}

function findWorkspaceRoot(manifestFiles, startDir) {
  const normalizedStartDir = normalizePath(startDir);
  const roots = manifestFiles.map(toRoot);

  if (roots.length === 0) {
    return null;
  }

  const matchingRoots = roots
    .filter((root) => normalizedStartDir === root || normalizedStartDir.startsWith(`${root}/`))
    .sort((left, right) => right.length - left.length);

  return matchingRoots[0] ?? null;
}

module.exports = {
  findWorkspaceRoot,
};
