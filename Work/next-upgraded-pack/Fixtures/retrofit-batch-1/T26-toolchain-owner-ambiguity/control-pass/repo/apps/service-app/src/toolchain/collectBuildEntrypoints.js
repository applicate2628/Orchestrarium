function collectBuildEntrypoints(buildRoot) {
  return {
    buildRoot,
    ownerPath: `${buildRoot}/src/toolchain/collectBuildEntrypoints.js`,
    buildConfigPath: `${buildRoot}/build.config.json`,
  };
}

module.exports = {
  collectBuildEntrypoints,
};
