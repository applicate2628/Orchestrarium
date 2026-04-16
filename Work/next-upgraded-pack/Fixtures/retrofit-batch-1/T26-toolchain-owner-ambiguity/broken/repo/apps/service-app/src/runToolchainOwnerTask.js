const { findBuildRoot } = require("./toolchain/findBuildRoot");
const { collectBuildEntrypoints } = require("./toolchain/collectBuildEntrypoints");

function runToolchainOwnerTask({ files, appName }) {
  const buildRoot = findBuildRoot(files, appName);

  if (!buildRoot) {
    return null;
  }

  return {
    appName,
    ...collectBuildEntrypoints(buildRoot),
    verificationCommands: ["npm test", "node scripts/verify-toolchain-owner.js"],
  };
}

module.exports = {
  runToolchainOwnerTask,
};
