function normalize(pathValue) {
  return pathValue.replace(/\\/g, "/");
}

function selectOwnerTarget({ basename, files }) {
  return files.map(normalize).find((entry) => entry.endsWith(`/${basename}`));
}

module.exports = {
  selectOwnerTarget,
};
