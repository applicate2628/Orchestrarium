function normalizePath(filePath) {
  return String(filePath ?? "").replace(/\\/g, "/").replace(/\/+$/g, "");
}

function toRoot(manifestPath) {
  const normalized = normalizePath(manifestPath);

  return normalized.endsWith("/package.json")
    ? normalized.slice(0, -"package.json".length - 1)
    : normalized;
}

function matchRoot(roots, candidatePath) {
  const normalizedCandidate = normalizePath(candidatePath);
  return roots.find((root) => normalizedCandidate === root || normalizedCandidate.startsWith(`${root}/`)) ?? null;
}

function recallWorkspaceRootAfterEdit({ previousRoot, manifestFiles, currentStartDir, priorEditPaths }) {
  const roots = manifestFiles.map(toRoot);
  const startMatch = matchRoot(roots, currentStartDir);

  if (startMatch) {
    return startMatch;
  }

  const lastTouchedRoot = [...(priorEditPaths ?? [])]
    .map((candidatePath) => matchRoot(roots, candidatePath))
    .filter(Boolean)
    .at(-1);

  if (lastTouchedRoot) {
    return lastTouchedRoot;
  }

  return roots.find((root) => root.includes("docs/")) ?? roots[0] ?? null;
}

module.exports = {
  recallWorkspaceRootAfterEdit,
};
