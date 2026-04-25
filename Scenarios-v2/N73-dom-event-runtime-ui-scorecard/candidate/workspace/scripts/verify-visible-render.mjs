import { createState } from "../src/state.mjs";
import { renderBoard } from "../src/view.mjs";

const items = [
  { id: "VIS-1", title: "Visible auth check", status: "blocked", owner: "Auth" },
  { id: "VIS-2", title: "Visible billing check", status: "ready", owner: "Billing" }
];

const markup = renderBoard(createState(items));
const errors = [];

if (!markup.includes('data-summary="true"')) {
  errors.push("summary marker missing");
}
if (!markup.includes("2 / 2 visible")) {
  errors.push("initial summary count is wrong");
}
if (!markup.includes('aria-live="polite"')) {
  errors.push("polite status region missing");
}
if (!markup.includes('data-filter="all"')) {
  errors.push("all filter button missing");
}

if (errors.length > 0) {
  for (const error of errors) {
    console.error(`ERROR: ${error}`);
  }
  process.exit(1);
}

console.log("N73 visible render PASS");
