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
  const answer = readJson("out/perf-memo.json");

  assert.deepEqual(answer, {
    trustBoundary: "archive-vs-mutable-workspace",
    keepScratchIgnored: true,
    redactProviderOutputs: true,
    providerStallClassification: "operational-blocker",
    prePublishCheck: "leak-check-staged-changes",
  });

  const packet = read("inputs/perf-packet.md");
  assert.match(packet, /archive and mutable work as separate trust surfaces/);
  assert.match(packet, /runtime stalls as operational blockers, not security incidents/);

  console.log("VERIFY_T06_SECURITY_MEMO_OK");
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
