export const previewStates = [
  { id: "loading", label: "Loading" },
  { id: "success", label: "Success" },
  { id: "empty", label: "Empty" },
  { id: "error", label: "Error" }
];

export const filterOptions = [
  { id: "all", label: "All checks" },
  { id: "attention", label: "Needs attention" },
  { id: "healthy", label: "Healthy only" },
  { id: "blocked", label: "Blocked" }
];

export const releaseChecks = [
  {
    id: "catalog-sync",
    title: "Catalog sync",
    status: "attention",
    statusLabel: "needs attention",
    description: "Catalog refresh is waiting on the delta import confirmation."
  },
  {
    id: "pricing-rollup",
    title: "Pricing rollup",
    status: "healthy",
    statusLabel: "healthy",
    description: "The latest price rollup landed in the release snapshot."
  },
  {
    id: "translation-audit",
    title: "Translation audit",
    status: "attention",
    statusLabel: "needs attention",
    description: "Two locales still require copy review before the launch cut."
  }
];

export function getFilterLabel(filterId) {
  return filterOptions.find((option) => option.id === filterId)?.label ?? filterId;
}

export function createBoardState(mode = "success", activeFilter = "all") {
  return {
    mode,
    activeFilter,
    checks: releaseChecks,
    selectedFilterLabel: getFilterLabel(activeFilter),
    errorMessage: "Release checks could not refresh.",
    lastUpdatedLabel: "Updated 3 minutes ago"
  };
}
