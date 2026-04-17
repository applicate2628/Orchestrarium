import { createBoardState, filterOptions, previewStates } from "./fixtures.js";
import { renderDashboard } from "./dashboard.js";

const previewModel = {
  mode: "success",
  activeFilter: "all"
};

const appRoot = document.querySelector("#app");
const stateToggleRoot = document.querySelector("#state-toggles");
const filterToggleRoot = document.querySelector("#filter-toggles");

function renderControlButtons(root, options, currentValue, attributes) {
  root.innerHTML = options
    .map((option) => {
      const active = option.id === currentValue;
      return `
        <button
          type="button"
          class="control-button${active ? " is-selected" : ""}"
          ${attributes.name}="${option.id}"
          aria-pressed="${active}"
        >
          ${option.label}
        </button>
      `;
    })
    .join("");
}

function renderPreview() {
  renderControlButtons(stateToggleRoot, previewStates, previewModel.mode, {
    name: "data-preview-state"
  });
  renderControlButtons(filterToggleRoot, filterOptions, previewModel.activeFilter, {
    name: "data-preview-filter"
  });

  const boardState = createBoardState(previewModel.mode, previewModel.activeFilter);
  appRoot.innerHTML = renderDashboard(boardState);
}

document.addEventListener("click", (event) => {
  const stateButton = event.target.closest("[data-preview-state]");
  if (stateButton) {
    previewModel.mode = stateButton.getAttribute("data-preview-state");
    renderPreview();
    return;
  }

  const previewFilterButton = event.target.closest("[data-preview-filter]");
  if (previewFilterButton) {
    previewModel.activeFilter = previewFilterButton.getAttribute("data-preview-filter");
    if (previewModel.mode !== "loading" && previewModel.mode !== "error") {
      previewModel.mode = previewModel.activeFilter === "blocked" ? "empty" : "success";
    }
    renderPreview();
    return;
  }

  const boardFilter = event.target.closest("[data-filter-value]");
  if (boardFilter) {
    previewModel.activeFilter = boardFilter.getAttribute("data-filter-value");
    previewModel.mode = previewModel.activeFilter === "blocked" ? "empty" : "success";
    renderPreview();
    return;
  }

  const resetButton = event.target.closest("[data-reset-filter]");
  if (resetButton) {
    previewModel.activeFilter = resetButton.getAttribute("data-reset-filter");
    previewModel.mode = "success";
    renderPreview();
    return;
  }

  const retryButton = event.target.closest("[data-retry-board]");
  if (retryButton) {
    previewModel.mode = "success";
    renderPreview();
  }
});

renderPreview();
