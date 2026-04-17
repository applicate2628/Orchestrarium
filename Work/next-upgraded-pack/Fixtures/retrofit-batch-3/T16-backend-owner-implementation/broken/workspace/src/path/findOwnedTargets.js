function findOwnedTargets(files, basename) {
  return files.filter((filePath) => filePath.endsWith(`/${basename}`));
}

module.exports = {
  findOwnedTargets,
};
