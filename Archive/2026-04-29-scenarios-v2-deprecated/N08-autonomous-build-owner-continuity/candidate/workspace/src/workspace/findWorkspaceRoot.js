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

  return roots.find((root) => !normalizedStartDir.startsWith(root)) ?? roots[0];
}

module.exports = {
  findWorkspaceRoot,
};
