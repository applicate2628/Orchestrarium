const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const { runPatchFlow } = require("../src/runPatchFlow");

function read(relativePath) {
  return fs.readFileSync(path.join(__dirname, "..", relativePath), "utf8");
}

try {
  const result = runPatchFlow({
    ownerScope: "workspace/src/providers",
    basename: "mergeLaneVerdict.js",
    candidates: [
      "workspace/docs/mergeLaneVerdict.js",
      "workspace/src/providers/mergeLaneVerdict.js",
      "workspace/legacy/mergeLaneVerdict.js",
    ],
    patchState: {
      steps: ["inspect failing row"],
      verificationCommands: ["node --test", "node scripts/verify-owner.js"],
    },
    nextStep: "patch owner seam",
    newSummary: "owner seam patched",
  });

  assert.equal(result.ownedTarget, "workspace/src/providers/mergeLaneVerdict.js");
  assert.deepEqual(result.steps, ["inspect failing row", "patch owner seam"]);
  assert.deepEqual(result.verificationCommands, ["node --test", "node scripts/verify-owner.js"]);

  assert.match(read("docs/chooseOwnedTarget.js"), /helper copy only/);
  assert.match(read("legacy/preserveVerificationPlan.js"), /verificationCommands: \["npm test"\]/);
  assert.match(read("scripts/chooseOwnedTarget.js"), /endsWith/);

  console.log("VERIFY_T32_PATCH_FLOW_OK");
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
