function cloneFields(fields) {
  return { ...fields };
}

export function createEditorState(items) {
  const normalized = items.map((item) => ({
    id: item.id,
    label: item.label,
    baseline: cloneFields(item.fields),
    draft: cloneFields(item.fields),
    errors: {},
  }));
  return {
    items: normalized,
    activeId: normalized[0]?.id ?? null,
    dirty: false,
    blockedNavigation: null,
    status: { type: "idle", text: "" },
    focusId: null,
  };
}

export function activeItem(state) {
  return state.items.find((item) => item.id === state.activeId) ?? null;
}

export function isDirty(state, itemId = state.activeId) {
  return state.activeId === itemId ? state.dirty : false;
}

function replaceActive(state, updater) {
  return {
    ...state,
    items: state.items.map((item) => (item.id === state.activeId ? updater(item) : item)),
  };
}

export function updateField(state, field, value) {
  return replaceActive(
    { ...state, dirty: true, status: { type: "idle", text: "" }, blockedNavigation: null },
    (item) => ({ ...item, draft: { ...item.draft, [field]: value }, errors: {} }),
  );
}

export function attemptNavigate(state, targetId) {
  const active = activeItem(state);
  return {
    ...state,
    activeId: targetId,
    dirty: false,
    blockedNavigation: null,
    status: { type: "idle", text: "" },
    items: state.items.map((item) =>
      item.id === active?.id ? { ...item, draft: cloneFields(item.baseline), errors: {} } : item,
    ),
  };
}

function validateDraft(item) {
  return {};
}

export function saveActive(state, result = { ok: true }) {
  const item = activeItem(state);
  if (!item) return state;
  const errors = validateDraft(item);
  if (Object.keys(errors).length > 0) {
    return replaceActive(
      { ...state, status: { type: "error", text: "Fix validation errors" }, focusId: null },
      (current) => ({ ...current, errors }),
    );
  }
  return replaceActive(
    { ...state, dirty: false, status: { type: "success", text: "Saved" }, focusId: null },
    (current) => ({ ...current, baseline: cloneFields(current.draft), errors: {} }),
  );
}

export function discardActive(state) {
  const first = state.items[0];
  return replaceActive(
    { ...state, dirty: false, blockedNavigation: null, status: { type: "idle", text: "" }, focusId: null },
    (current) => ({ ...current, draft: cloneFields(first.baseline), errors: {} }),
  );
}
