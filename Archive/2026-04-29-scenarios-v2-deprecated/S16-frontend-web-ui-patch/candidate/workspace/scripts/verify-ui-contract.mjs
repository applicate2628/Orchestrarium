import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { createBoardState } from "../src/fixtures.js";
import { renderDashboard } from "../src/dashboard.js";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const cssText = readFileSync(path.resolve(scriptDir, "../src/dashboard.css"), "utf8");
const errors = [];

function requireCondition(condition, message) {
  if (!condition) {
    errors.push(message);
  }
}

const loadingMarkup = renderDashboard(createBoardState("loading", "all"));
requireCondition(loadingMarkup.includes('role="status"'), "Loading state is missing role=status");
requireCondition(
  loadingMarkup.includes('aria-live="polite"'),
  "Loading state is missing aria-live=polite"
);
requireCondition(
  loadingMarkup.includes("Loading release checks..."),
  "Loading state copy does not match the required text"
);

const successMarkup = renderDashboard(createBoardState("success", "attention"));
requireCondition(
  successMarkup.includes("<button") &&
    successMarkup.includes('class="filter-chip') &&
    successMarkup.includes('data-filter-value="attention"') &&
    successMarkup.includes('aria-pressed="true"'),
  "Success state is missing semantic filter buttons with pressed state"
);
requireCondition(
  successMarkup.includes('id="board-summary"'),
  "Success state is missing the board summary id"
);
requireCondition(
  successMarkup.includes('aria-describedby="board-summary"'),
  "Success list is missing aria-describedby=board-summary"
);
requireCondition(
  successMarkup.includes("Showing 2 checks"),
  "Success state summary text is incorrect for the attention filter"
);
requireCondition(
  successMarkup.includes('aria-label="Catalog sync, needs attention"'),
  "Result card accessibility labels are missing or incomplete"
);

const emptyMarkup = renderDashboard(createBoardState("empty", "blocked"));
requireCondition(
  emptyMarkup.includes("No checks match this filter"),
  "Empty state heading is incorrect"
);
requireCondition(
  emptyMarkup.includes("Blocked"),
  "Empty state does not mention the selected filter label"
);
requireCondition(
  emptyMarkup.includes("<button") && emptyMarkup.includes('data-reset-filter="all"'),
  "Empty state reset action is missing"
);
requireCondition(
  emptyMarkup.includes("Reset to all checks"),
  "Empty state reset copy is incorrect"
);

const errorMarkup = renderDashboard(createBoardState("error", "all"));
requireCondition(errorMarkup.includes('role="alert"'), "Error state is missing role=alert");
requireCondition(errorMarkup.includes("Retry checks"), "Error retry copy is incorrect");
requireCondition(
  !errorMarkup.includes('class="check-list"'),
  "Error state still renders stale result cards"
);

requireCondition(
  cssText.includes('.filter-chip[aria-pressed="true"]'),
  "CSS is missing the active pressed-state selector"
);
requireCondition(
  cssText.includes(".filter-chip:focus-visible"),
  "CSS is missing a visible focus rule for filter controls"
);
requireCondition(
  cssText.includes(".board__secondary-action:focus-visible"),
  "CSS is missing a visible focus rule for the empty-state reset action"
);
requireCondition(
  cssText.includes(".board__primary-action:focus-visible"),
  "CSS is missing a visible focus rule for the retry action"
);

if (errors.length > 0) {
  for (const error of errors) {
    console.error(`ERROR: ${error}`);
  }
  process.exit(1);
}

console.log("S16 UI contract PASS");
