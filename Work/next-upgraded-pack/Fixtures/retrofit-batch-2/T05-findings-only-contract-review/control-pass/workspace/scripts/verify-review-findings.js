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
  const findings = readJson("out/findings.json");

  assert.deepEqual(findings, [
    {
      severity: "high",
      mechanism: "unsupported-gemini-runtime-target",
      file: "work-items/active/2026-04-13-mcp-impact-role-provider-benchmarking/plan.md",
    },
    {
      severity: "high",
      mechanism: "promotes-fallback-transport-into-provider-order",
      file: "work-items/active/2026-04-13-mcp-impact-role-provider-benchmarking/matrices/model-verdict-to-lane-priority-mapping.md",
    },
    {
      severity: "medium",
      mechanism: "reorders-execution-toward-fallback-wave-before-remaining-top-path-work",
      file: "work-items/active/2026-04-13-mcp-impact-role-provider-benchmarking/status.md",
    },
  ]);

  const packet = read("inputs/review-packet.md");
  assert.match(packet, /gemini-3\.1-pro-preview/);
  assert.match(packet, /wording from `more generic` to `a bit more generic`/);

  console.log("VERIFY_T05_FINDINGS_OK");
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
