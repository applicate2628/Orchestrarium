import { visibleItems } from "./state.mjs";

const FILTERS = [
  ["all", "All"],
  ["blocked", "Blocked"],
  ["ready", "Ready"]
];

export function renderBoard(state) {
  const visible = visibleItems(state);
  const cards = state.items
    .map((item) => {
      const isVisible = visible.includes(item);
      const dirty = state.dirtyIds.has(item.id);
      return `<article class="card" data-card-id="${item.id}" data-visible="${isVisible ? "true" : "false"}" data-dirty="${dirty ? "true" : "false"}">
        <h3>${item.title}</h3>
        <p>${item.status} · ${item.owner}</p>
        <button type="button" data-dirty-toggle="${item.id}" aria-pressed="${dirty ? "true" : "false"}">Mark dirty</button>
      </article>`;
    })
    .join("");

  const filters = FILTERS.map(([value, label]) => {
    const pressed = state.filter === value ? "true" : "false";
    return `<button type="button" data-filter="${value}" aria-pressed="${pressed}">${label}</button>`;
  }).join("");

  const disabled = state.dirtyIds.size === 0 ? "disabled" : "";
  return `<section class="board">
    <nav data-filter-bar="true">${filters}</nav>
    <p data-summary="true">${visible.length} / ${state.items.length} visible</p>
    <div data-card-list="true">${cards}</div>
    <button type="button" data-save="true" ${disabled}>Save changes</button>
    <p data-status="true" aria-live="polite">${state.statusText}</p>
  </section>`;
}

export function renderInto(root, state, handlers) {
  root.innerHTML = renderBoard(state);
  for (const button of root.querySelectorAll("[data-filter]")) {
    button.addEventListener("click", () => handlers.onFilter(button.getAttribute("data-filter")));
  }
  for (const button of root.querySelectorAll("[data-dirty-toggle]")) {
    button.addEventListener("click", () => handlers.onToggle(button.getAttribute("data-dirty-toggle")));
  }
  const save = root.querySelector("[data-save]");
  save.addEventListener("click", handlers.onSave);
}
