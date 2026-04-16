function normalizePath(filePath) {
  return filePath.replace(/\\/g, "/");
}

function findBuildRoot(files, appName) {
  const roots = files
    .map(normalizePath)
    .filter((filePath) => filePath.endsWith("/build.config.json") && filePath.includes(appName))
    .map((filePath) => filePath.slice(0, -"/build.config.json".length));

  if (roots.length === 0) {
    return null;
  }

  return roots.find((rootPath) => rootPath.includes(`${appName}-shadow`)) ?? roots[0];
}

module.exports = {
  findBuildRoot,
};
