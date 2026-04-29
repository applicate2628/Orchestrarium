function normalizePath(filePath) {
  return String(filePath ?? "").replace(/\\/g, "/").replace(/\/+$/g, "");
}

function toRoot(manifestPath) {
  const normalized = normalizePath(manifestPath);

  return normalized.endsWith("/package.json")
    ? normalized.slice(0, -"package.json".length - 1)
    : normalized;
}

function findInitialWorkspaceRoot(manifestFiles, startDir) {
  const normalizedStartDir = normalizePath(startDir);
  const roots = manifestFiles.map(toRoot);

  return roots.find((root) => normalizedStartDir === root || normalizedStartDir.startsWith(`${root}/`)) ?? null;
}

module.exports = {
  findInitialWorkspaceRoot,
};
