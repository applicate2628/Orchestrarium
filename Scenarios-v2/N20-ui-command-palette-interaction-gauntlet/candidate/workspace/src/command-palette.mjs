import { visibleActions } from "./palette-state.mjs";

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

export function renderPalette(state) {
  const visible = visibleActions(state);
  const options = visible
    .map((action) => {
      const selected = action.id === state.activeId;
      return `<button class="palette-option" role="option" data-owner="${escapeHtml(action.owner)}" aria-selected="${selected ? "true" : "false"}">${escapeHtml(action.label)}</button>`;
    })
    .join("");
  return `<section class="palette" role="listbox">${options}</section>`;
}
