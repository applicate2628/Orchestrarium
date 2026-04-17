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
  const answer = readJson("out/ui-triage.json");

  assert.deepEqual(answer, {
    findings: [
      {
        id: "global-priority-badge-dominates-layout",
        severity: "high",
        impact: "lane-reading-is-visually-overpowered",
      },
      {
        id: "confidence-note-is-underemphasized",
        severity: "medium",
        impact: "important-caveats-are-easy-to-miss",
      },
      {
        id: "decorative-crowns-repeat-without-meaning",
        severity: "low",
        impact: "decorative-noise-outweighs-signal",
      },
    ],
    nextFixOrder: [
      "reduce-global-priority-badge-weight",
      "restore-confidence-note-emphasis",
      "remove-or-justify-repeated-crowns",
    ],
    doNotUseAsSingleFix: "color-adjustment-only",
  });

  const notes = read("inputs/triage-notes.md");
  const contract = read("inputs/interaction-contract.md");
  assert.match(notes, /only tuned colors/);
  assert.match(contract, /Lane-specific reading must remain stronger/);

  console.log("VERIFY_T20_VISUAL_REVIEW_OK");
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
