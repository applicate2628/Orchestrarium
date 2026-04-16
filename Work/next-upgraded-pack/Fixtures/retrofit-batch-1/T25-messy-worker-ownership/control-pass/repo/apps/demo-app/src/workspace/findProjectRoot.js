function normalizePath(filePath) {
  return String(filePath ?? "").replace(/\\/g, "/").replace(/\/+$/g, "");
}

function toRoot(manifestPath) {
  const normalized = normalizePath(manifestPath);

  return normalized.endsWith("/package.json")
    ? normalized.slice(0, -"package.json".length - 1)
    : normalized;
}

function findProjectRoot(manifestFiles, startDir) {
  const normalizedStartDir = normalizePath(startDir);
  const roots = manifestFiles.map(toRoot);
  const matches = roots.filter(
    (root) => normalizedStartDir === root || normalizedStartDir.startsWith(`${root}/`)
  );

  if (matches.length === 0) {
    return null;
  }

  return matches.sort((left, right) => right.length - left.length)[0];
}

module.exports = {
  findProjectRoot,
};
