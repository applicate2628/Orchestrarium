function normalizePath(filePath) {
  return filePath.replace(/\\/g, "/");
}

function resolveFollowupTarget(session, basename) {
  const files = session.availableFiles.map(normalizePath);
  const scoped = files.filter(
    (filePath) => filePath.startsWith(`${session.ownerScope}/`) && filePath.endsWith(`/${basename}`)
  );

  if (scoped.length > 0) {
    return scoped[0];
  }

  return files.find((filePath) => filePath.endsWith(`/${basename}`)) ?? null;
}

module.exports = {
  resolveFollowupTarget,
};
