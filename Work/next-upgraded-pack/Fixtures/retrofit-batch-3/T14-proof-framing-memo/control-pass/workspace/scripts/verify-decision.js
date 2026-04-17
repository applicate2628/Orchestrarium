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
    invariants: [
      "archive-remains-frozen",
      "scratch-broken-copy-is-only-run-root",
      "pass-requires-verifier-green",
      "ranking-change-requires-execution-evidence",
    ],
    forbiddenShortcut: "count-blocked-or-unrun-tests-as-fails",
    proofGoal: "justify-full-registry-read-with-explicit-evidence",
  });

  const packet = read("inputs/adr-packet.md");
  assert.match(packet, /the archive remains frozen/);
  assert.match(packet, /do not count blocked or unrun tests as failures/);

  console.log("VERIFY_T14_PROOF_MEMO_OK");
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
