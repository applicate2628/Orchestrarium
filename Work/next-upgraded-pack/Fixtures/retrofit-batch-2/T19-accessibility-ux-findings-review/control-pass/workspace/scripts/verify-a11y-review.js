const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function read(relativePath) {
  return fs.readFileSync(path.join(__dirname, "..", relativePath), "utf8");
}

function readJson(relativePath) {
  return JSON.parse(read(relativePath));
}

try {
  const answer = readJson("out/a11y-review.json");

  assert.deepEqual(answer, {
    findings: [
      {
        id: "global-best-provider-conflicts-with-lane-specific-flow",
        severity: "high",
        impact: "operator-may-overtrust-a-global-winner",
      },
      {
        id: "focusable-card-without-action",
        severity: "medium",
        impact: "keyboard-users-stop-on-a-non-interactive-block",
      },
      {
        id: "low-confidence-note-has-low-contrast",
        severity: "medium",
        impact: "confidence-note-is-hard-to-read",
      },
    ],
    nextFixOrder: [
      "global-best-provider-conflicts-with-lane-specific-flow",
      "focusable-card-without-action",
      "low-confidence-note-has-low-contrast",
    ],
  });

  const flows = read("inputs/user-flows.md");
  const html = read("inputs/review-target.html");
  assert.match(flows, /which provider to use for a planned design task/);
  assert.match(html, /<div class=\"card\" tabindex=\"0\">/);
  assert.match(html, /color:#9aa0a6; background:#ffffff/);

  console.log("VERIFY_T19_A11Y_REVIEW_OK");
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
