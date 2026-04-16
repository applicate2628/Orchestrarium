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
  const normalizedPreviousRoot = normalizePath(previousRoot);

  if (normalizedPreviousRoot && roots.includes(normalizedPreviousRoot)) {
    return normalizedPreviousRoot;
  }

  const startMatch = matchRoot(roots, currentStartDir);
  if (startMatch) {
    return startMatch;
  }

  const matchedPriorRoots = [...(priorEditPaths ?? [])]
    .map((candidatePath) => matchRoot(roots, candidatePath))
    .filter(Boolean);

  if (matchedPriorRoots.length === 0) {
    return null;
  }

  const counts = new Map();
  for (const root of matchedPriorRoots) {
    counts.set(root, (counts.get(root) ?? 0) + 1);
  }

  return [...counts.entries()]
    .sort((left, right) => {
      if (right[1] !== left[1]) {
        return right[1] - left[1];
      }

      return roots.indexOf(left[0]) - roots.indexOf(right[0]);
    })[0]?.[0] ?? null;
}

module.exports = {
  recallWorkspaceRootAfterEdit,
};
