function normalizePath(filePath) {
  return filePath.replace(/\\/g, "/");
}

function findCommonPath(paths) {
  const segmentSets = paths.map((filePath) => normalizePath(filePath).split("/"));

  if (segmentSets.length === 0) {
    return null;
  }

  const shared = [];
  const shortest = Math.min(...segmentSets.map((segments) => segments.length));

  for (let index = 0; index < shortest; index += 1) {
    const candidate = segmentSets[0][index];

    if (segmentSets.every((segments) => segments[index] === candidate)) {
      shared.push(candidate);
      continue;
    }

    break;
  }

  return shared.length > 0 ? shared.join("/") : null;
}

function carryForwardOwnerScope(session) {
  const normalizedScope = session.ownerScope ? normalizePath(session.ownerScope) : null;
  const repairedDirs = (session.repairedFiles ?? []).map((filePath) => {
    const normalized = normalizePath(filePath);
    return normalized.slice(0, normalized.lastIndexOf("/"));
  });

  if (
    normalizedScope &&
    repairedDirs.length > 0 &&
    repairedDirs.every(
      (directoryPath) => directoryPath === normalizedScope || directoryPath.startsWith(`${normalizedScope}/`)
    )
  ) {
    return {
      ...session,
      ownerScope: normalizedScope,
    };
  }

  return {
    ...session,
    ownerScope: findCommonPath(repairedDirs) ?? normalizedScope,
  };
}

module.exports = {
  carryForwardOwnerScope,
};
