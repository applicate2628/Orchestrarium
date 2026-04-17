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
  const answer = readJson("out/decision.json");

  assert.deepEqual(answer, {
    decision: "keep-provider-order-at-provider-level",
    fallbackHandling: "provider-local-path-notes",
    transportHandling: "transport-is-not-provider",
    providerUniverse: ["codex", "claude", "gemini"],
    mcpScoring: "deferred",
  });

  const packet = read("inputs/adr-packet.md");
  assert.match(packet, /`claude-api` is a secondary Claude transport, not a fourth provider/);
  assert.match(packet, /do not propose MCP scoring/);

  console.log("VERIFY_T03_DECISION_OK");
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
