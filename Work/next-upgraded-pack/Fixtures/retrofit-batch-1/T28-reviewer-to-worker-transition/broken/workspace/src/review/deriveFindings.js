function deriveFindings(reviewSet = "main") {
  const findingsBySet = {
    main: [
      {
        id: "F1",
        file: "workspace/src/routing/lanePriorityResolver.js",
        summary: "resolver prefers docs lane before the real app lane",
        severity: "high",
      },
      {
        id: "F2",
        file: "workspace/docs/lanePriorityResolver.js",
        summary: "docs example is stale",
        severity: "low",
      },
      {
        id: "F5",
        file: "workspace/legacy/lanePriorityResolver.js",
        summary: "legacy example is stale",
        severity: "low",
      },
    ],
    feature: [
      {
        id: "F3",
        file: "workspace/src/feature-space/routing/lanePriorityResolver.js",
        summary: "feature resolver prefers docs lane before the real app lane",
        severity: "high",
      },
      {
        id: "F4",
        file: "workspace/docs/feature-space/lanePriorityResolver.js",
        summary: "feature docs example is stale",
        severity: "low",
      },
      {
        id: "F6",
        file: "workspace/legacy/feature-space/lanePriorityResolver.js",
        summary: "feature legacy example is stale",
        severity: "low",
      },
    ],
  };

  return findingsBySet[reviewSet] ?? [];
}

module.exports = {
  deriveFindings,
};
