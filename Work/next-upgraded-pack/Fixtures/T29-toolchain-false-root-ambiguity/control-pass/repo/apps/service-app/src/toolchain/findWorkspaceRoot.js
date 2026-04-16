function normalize(pathValue) {
  return pathValue.replace(/\\/g, "/");
}

function stripManifestSuffix(manifestPath) {
  return normalize(manifestPath).replace(/\/package\.json$/, "");
}

function findWorkspaceRoot({ manifestFiles, startDir }) {
  const normalizedStart = normalize(startDir);
  const roots = manifestFiles.map(stripManifestSuffix);
  const directOwner = roots
    .filter((root) => normalizedStart === root || normalizedStart.startsWith(`${root}/`))
    .sort((left, right) => right.length - left.length)[0];

  if (directOwner) {
    return directOwner;
  }

  return roots.sort((left, right) => right.length - left.length)[0];
}

module.exports = {
  findWorkspaceRoot,
};
