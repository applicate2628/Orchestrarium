const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function readJson(relativePath) {
  return JSON.parse(fs.readFileSync(path.join(__dirname, "..", relativePath), "utf8"));
}

function read(relativePath) {
  return fs.readFileSync(path.join(__dirname, "..", relativePath), "utf8");
}

try {
  const answer = readJson("out/facts.json");

  assert.deepEqual(answer, {
    activeTrack: "model-only",
    deferredTrack: "mcp-impact",
    w1Targets: ["X3", "X4", "X1", "X5"],
    workflowOutput: "workflow-lane priority map",
    x3x4Interpretation: "claude-path-note-first",
  });

  const source = read("inputs/source-excerpt.md");
  assert.match(source, /active track: `model-only`/);
  assert.match(source, /deferred track: `mcp-impact`/);
  assert.match(source, /`W1` targets: `X3`, `X4`, `X1`, `X5`/);

  console.log("VERIFY_T01_FACTS_OK");
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
