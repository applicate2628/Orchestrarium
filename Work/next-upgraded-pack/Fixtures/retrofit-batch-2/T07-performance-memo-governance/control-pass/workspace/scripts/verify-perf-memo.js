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
  const memo = readJson("out/perf-memo.json");

  assert.deepEqual(memo, {
    primaryBudgetSignal: "per-run-cost-ceiling",
    requiredMetrics: ["duration_ms", "total_cost_usd", "tools.totalCalls"],
    noiseHandling: "record-envelope-noise-separately",
    replayRequirement: "fresh-worktree-and-ci-replay",
    overCeilingHandling: "keep-fallback-path-valid-but-fallback-only",
  });

  const packet = read("inputs/perf-packet.md");
  assert.match(packet, /plugin-sync/);
  assert.match(packet, /tools.totalCalls = 0/);

  console.log("VERIFY_T07_PERF_MEMO_OK");
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
