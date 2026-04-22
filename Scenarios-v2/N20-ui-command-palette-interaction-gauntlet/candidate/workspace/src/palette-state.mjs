export function createPaletteState(actions) {
  return {
    actions: actions.map((action) => ({ ...action })),
    query: "",
    activeId: actions[0]?.id ?? null,
    lastStableActiveId: actions[0]?.id ?? null,
    selected: null,
  };
}

export function visibleActions(state) {
  const query = state.query.trim().toLowerCase();
  if (!query) {
    return state.actions;
  }
  return state.actions.filter((action) => action.label.toLowerCase().includes(query));
}

export function moveFocus(state, direction) {
  const visible = visibleActions(state);
  if (visible.length === 0) {
    return { ...state, activeId: null };
  }
  const index = visible.findIndex((action) => action.id === state.activeId);
  const nextIndex = direction === "up" ? Math.max(0, index - 1) : Math.min(visible.length - 1, index + 1);
  const active = visible[nextIndex] ?? visible[0];
  return { ...state, activeId: active.id, lastStableActiveId: active.id };
}

export function applyFilter(state, query) {
  const next = { ...state, query };
  const visible = visibleActions(next);
  return { ...next, activeId: visible[0]?.id ?? null };
}

export function clearFilter(state) {
  return { ...state, query: "", activeId: state.actions[0]?.id ?? null };
}

export function selectActive(state) {
  const action = state.actions.find((item) => item.id === state.activeId);
  return { ...state, selected: action?.id ?? null };
}
