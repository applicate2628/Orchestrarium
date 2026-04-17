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
  const answer = readJson("out/build-diagnosis.json");

  assert.deepEqual(answer, {
    rootCause: "render-step-assumes-generated-provider-order-artifact-already-exists",
    firstFailureLayer: "missing-generated-input-before-render",
    smallestSafeFix: "initialize-or-generate-.scratch-generated-provider-order-json-before-render",
    reproCase: "fresh-worktree-or-ci",
    doNotBlame: "last-visible-enoent-alone",
  });

  const packet = read("inputs/build-break.md");
  assert.match(packet, /CI fails deterministically/);
  assert.match(packet, /benchmark cache root not initialized/);

  console.log("VERIFY_T15_BUILD_DIAGNOSIS_OK");
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
