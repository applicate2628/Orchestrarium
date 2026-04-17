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
    phaseOrder: ["build-fixtures", "local-validation", "run-x1-x2-x3", "refresh-results"],
    activeRows: ["X1", "X2", "X3"],
    samePassDefers: ["X5", "X6"],
    archiveMutation: false,
    rerankBeforeEvidence: false,
  });

  const packet = read("inputs/adr-packet.md");
  assert.match(packet, /finish the remaining extended tests and run them/);
  assert.match(packet, /do not reopen `X5` or `X6` in the same pass/);

  console.log("VERIFY_T04_PLAN_OK");
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
