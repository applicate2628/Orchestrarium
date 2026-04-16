function normalizePath(filePath) {
  return filePath.replace(/\\/g, "/");
}

function carryForwardOwnerScope(session) {
  const lastFile = normalizePath(session.repairedFiles.at(-1));
  const narrowedScope = lastFile.slice(0, lastFile.lastIndexOf("/"));

  return {
    ...session,
    ownerScope: narrowedScope,
  };
}

module.exports = {
  carryForwardOwnerScope,
};
