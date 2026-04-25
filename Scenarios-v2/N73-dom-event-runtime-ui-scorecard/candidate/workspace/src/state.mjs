export function createState(items) {
  return {
    items,
    filter: "all",
    dirtyIds: new Set(),
    statusText: "No unsaved changes"
  };
}

export function visibleItems(state) {
  return state.items;
}

export function setFilter(state, filter) {
  state.filter = filter;
}

export function toggleDirty(state, id) {
  state.dirtyIds = new Set([id]);
  state.statusText = "Unsaved changes";
}

export function saveChanges(state) {
  state.statusText = "Saved";
}
