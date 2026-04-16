function stripManifestSuffix(manifestPath) {
  return manifestPath.replace(/\/package\.json$/, "");
}

function findWorkspaceRoot({ manifestFiles }) {
  const appManifest = manifestFiles.find((entry) => entry.includes("/apps/"));

  if (appManifest) {
    return stripManifestSuffix(appManifest);
  }

  return stripManifestSuffix(manifestFiles[0]);
}

module.exports = {
  findWorkspaceRoot,
};
