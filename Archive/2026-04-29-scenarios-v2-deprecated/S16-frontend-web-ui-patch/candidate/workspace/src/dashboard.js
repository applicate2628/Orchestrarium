import { filterOptions } from "./fixtures.js";
import { copy } from "./ui-copy.js";

function getVisibleChecks(state) {
  if (state.mode === "empty") {
    return [];
  }

  if (state.activeFilter === "all") {
    return state.checks;
  }

  return state.checks.filter((check) => check.status === state.activeFilter);
}

function renderFilters(activeFilter) {
  return `
    <div class="filter-row" aria-label="Check filters">
      ${filterOptions
        .map(
          (filter) => `
            <div
              class="filter-chip${filter.id === activeFilter ? " is-active" : ""}"
              data-filter-value="${filter.id}"
            >
              ${filter.label}
            </div>
          `
        )
        .join("")}
    </div>
  `;
}

function renderCheckList(checks) {
  return `
    <ul class="check-list">
      ${checks
        .map(
          (check) => `
            <li class="check-card">
              <div class="check-card__header">
                <h3>${check.title}</h3>
                <span class="check-card__status check-card__status--${check.status}">
                  ${check.statusLabel}
                </span>
              </div>
              <p>${check.description}</p>
            </li>
          `
        )
        .join("")}
    </ul>
  `;
}

function renderLoadingState(state) {
  return `
    <section class="board board--loading" aria-labelledby="board-heading">
      <div class="board__header">
        <div>
          <h2 id="board-heading">${copy.heading}</h2>
          <p class="board__meta">${state.lastUpdatedLabel}</p>
        </div>
        ${renderFilters(state.activeFilter)}
      </div>
      <p class="board__message">${copy.loadingLabel}</p>
    </section>
  `;
}

function renderEmptyState(state) {
  return `
    <section class="board board--empty" aria-labelledby="board-heading">
      <div class="board__header">
        <div>
          <h2 id="board-heading">${copy.heading}</h2>
          <p class="board__meta">${state.lastUpdatedLabel}</p>
        </div>
        ${renderFilters(state.activeFilter)}
      </div>
      <div class="board__message board__message--empty">
        <h3>${copy.emptyHeading}</h3>
        <p>${copy.emptyBody}</p>
      </div>
    </section>
  `;
}

function renderErrorState(state, checks) {
  return `
    <section class="board board--error" aria-labelledby="board-heading">
      <div class="board__header">
        <div>
          <h2 id="board-heading">${copy.heading}</h2>
          <p class="board__meta">${state.lastUpdatedLabel}</p>
        </div>
        ${renderFilters(state.activeFilter)}
      </div>
      <div class="board__message board__message--error">
        <h3>${copy.errorHeading}</h3>
        <p>${state.errorMessage}</p>
        <button type="button" class="board__primary-action" data-retry-board="true">
          ${copy.retryLabel}
        </button>
      </div>
      ${renderCheckList(checks)}
    </section>
  `;
}

function renderSuccessState(state, checks) {
  return `
    <section class="board" aria-labelledby="board-heading">
      <div class="board__header">
        <div>
          <h2 id="board-heading">${copy.heading}</h2>
          <p class="board__meta">${state.lastUpdatedLabel}</p>
        </div>
        ${renderFilters(state.activeFilter)}
      </div>
      <p class="board__summary">${copy.summaryLabel(checks.length)}</p>
      ${renderCheckList(checks)}
    </section>
  `;
}

export function renderDashboard(state) {
  const visibleChecks = getVisibleChecks(state);

  if (state.mode === "loading") {
    return renderLoadingState(state);
  }

  if (state.mode === "error") {
    return renderErrorState(state, visibleChecks);
  }

  if (visibleChecks.length === 0) {
    return renderEmptyState(state);
  }

  return renderSuccessState(state, visibleChecks);
}
