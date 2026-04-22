import { activeItem, isDirty } from "./editor-state.mjs";

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

export function renderEditor(state) {
  const item = activeItem(state);
  if (!item) {
    return `<section class="editor" data-empty="true"></section>`;
  }
  const dirty = isDirty(state, item.id);
  const status = state.status.text ? `<p class="status">${escapeHtml(state.status.text)}</p>` : "";
  return `<section class="editor" data-active-id="${escapeHtml(item.id)}" data-dirty="${dirty ? "true" : "false"}">
    <nav class="editor-tabs">
      ${state.items.map((entry) => `<button data-route="${escapeHtml(entry.id)}">${escapeHtml(entry.label)}</button>`).join("")}
    </nav>
    ${status}
    <label>Title <input name="title" value="${escapeHtml(item.draft.title)}"></label>
    <label>Slug <input name="slug" value="${escapeHtml(item.draft.slug)}"></label>
    <label>Summary <textarea name="summary">${escapeHtml(item.draft.summary)}</textarea></label>
    <footer class="editor-actions">
      <button data-action="save"${dirty ? "" : " disabled"}>Save changes</button>
      <button data-action="discard"${dirty ? "" : " disabled"}>Discard changes</button>
    </footer>
  </section>`;
}
