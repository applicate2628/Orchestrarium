const test = require("node:test");
const assert = require("node:assert/strict");

const { runPatchFlow } = require("../src/runPatchFlow");

test("keeps the real owned target inside the owner scope", () => {
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
});

test("appends the new step instead of replacing existing repair history", () => {
  const result = runPatchFlow({
    ownerScope: "workspace/src/providers",
    basename: "mergeLaneVerdict.js",
    candidates: [
      "workspace/src/providers/mergeLaneVerdict.js",
    ],
    patchState: {
      steps: ["inspect failing row"],
      verificationCommands: ["node --test", "node scripts/verify-owner.js"],
    },
    nextStep: "patch owner seam",
    newSummary: "owner seam patched",
  });

  assert.deepEqual(result.steps, ["inspect failing row", "patch owner seam"]);
});

test("preserves the full verification plan instead of collapsing to a smoke-only check", () => {
  const result = runPatchFlow({
    ownerScope: "workspace/src/providers",
    basename: "mergeLaneVerdict.js",
    candidates: [
      "workspace/src/providers/mergeLaneVerdict.js",
    ],
    patchState: {
      steps: ["inspect failing row"],
      verificationCommands: ["node --test", "node scripts/verify-owner.js"],
    },
    nextStep: "patch owner seam",
    newSummary: "owner seam patched",
  });

  assert.deepEqual(result.verificationCommands, ["node --test", "node scripts/verify-owner.js"]);
});
