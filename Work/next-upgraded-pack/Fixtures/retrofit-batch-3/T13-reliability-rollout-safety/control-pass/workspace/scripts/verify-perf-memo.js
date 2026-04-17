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
    failureModes: [
      "provider-runtime-stall",
      "owner-seam-scope-widening",
      "result-surface-refresh-without-evidence",
    ],
    mitigations: [
      "treat-runtime-stall-as-blocked",
      "enforce-owner-seam-verifiers",
      "commit-after-completed-pass",
    ],
    publishGate: "update-evidence-before-results",
    blockerPolicy: "runtime-stall-is-blocked-not-fail",
  });

  const packet = read("inputs/perf-packet.md");
  assert.match(packet, /runtime stalls must not silently demote a row/);
  assert.match(packet, /results should refresh only after evidence is written/);

  console.log("VERIFY_T13_RELIABILITY_MEMO_OK");
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
