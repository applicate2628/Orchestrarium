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

test("does not accept a sibling prefix as the owner scope", () => {
  const result = runPatchFlow({
    ownerScope: "workspace/src/providers",
    basename: "mergeLaneVerdict.js",
    candidates: [
      "workspace/src/providers-extra/mergeLaneVerdict.js",
      "workspace/src/providers/mergeLaneVerdict.js",
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

test("normalizes Windows separators before checking the owner scope", () => {
  const result = runPatchFlow({
    ownerScope: "workspace/src/providers",
    basename: "mergeLaneVerdict.js",
    candidates: [
      "workspace\\docs\\mergeLaneVerdict.js",
      "workspace\\src\\providers\\mergeLaneVerdict.js",
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

test("accepts nested files inside the owner scope instead of exact one-level targets only", () => {
  const result = runPatchFlow({
    ownerScope: "workspace/src/providers",
    basename: "mergeLaneVerdict.js",
    candidates: [
      "workspace/docs/mergeLaneVerdict.js",
      "workspace/src/providers/claude/mergeLaneVerdict.js",
    ],
    patchState: {
      steps: ["inspect failing row"],
      verificationCommands: ["node --test", "node scripts/verify-owner.js"],
    },
    nextStep: "patch owner seam",
    newSummary: "owner seam patched",
  });

  assert.equal(result.ownedTarget, "workspace/src/providers/claude/mergeLaneVerdict.js");
});

test("returns null when no candidate is inside the owner scope", () => {
  const result = runPatchFlow({
    ownerScope: "workspace/src/providers",
    basename: "mergeLaneVerdict.js",
    candidates: [
      "workspace/docs/mergeLaneVerdict.js",
      "workspace/legacy/mergeLaneVerdict.js",
    ],
    patchState: {
      steps: ["inspect failing row"],
      verificationCommands: ["node --test", "node scripts/verify-owner.js"],
    },
    nextStep: "patch owner seam",
    newSummary: "owner seam patched",
  });

  assert.equal(result.ownedTarget, null);
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

test("preserves all previous patch steps and does not mutate input state", () => {
  const patchState = {
    steps: ["inspect failing row", "confirm owner scope"],
    verificationCommands: ["node --test", "node scripts/verify-owner.js"],
  };

  const result = runPatchFlow({
    ownerScope: "workspace/src/providers",
    basename: "mergeLaneVerdict.js",
    candidates: [
      "workspace/src/providers/mergeLaneVerdict.js",
    ],
    patchState,
    nextStep: "patch owner seam",
    newSummary: "owner seam patched",
  });

  assert.deepEqual(result.steps, ["inspect failing row", "confirm owner scope", "patch owner seam"]);
  assert.deepEqual(patchState.steps, ["inspect failing row", "confirm owner scope"]);
  assert.notEqual(result.steps, patchState.steps);
});

test("preserves the full verification plan instead of collapsing to a smoke-only check", () => {
  const patchState = {
    steps: ["inspect failing row"],
    verificationCommands: ["node --test", "node scripts/verify-owner.js"],
  };

  const result = runPatchFlow({
    ownerScope: "workspace/src/providers",
    basename: "mergeLaneVerdict.js",
    candidates: [
      "workspace/src/providers/mergeLaneVerdict.js",
    ],
    patchState,
    nextStep: "patch owner seam",
    newSummary: "owner seam patched",
  });

  assert.deepEqual(result.verificationCommands, ["node --test", "node scripts/verify-owner.js"]);
  assert.notEqual(result.verificationCommands, patchState.verificationCommands);
});

test("preserves extra verification commands and patch metadata", () => {
  const patchState = {
    steps: ["inspect failing row"],
    verificationCommands: ["node --test", "node scripts/verify-owner.js", "node scripts/check-scope.js"],
    riskOwner: "worker.long-autonomous",
  };

  const result = runPatchFlow({
    ownerScope: "workspace/src/providers",
    basename: "mergeLaneVerdict.js",
    candidates: [
      "workspace/src/providers/mergeLaneVerdict.js",
    ],
    patchState,
    nextStep: "patch owner seam",
    newSummary: "owner seam patched",
  });

  assert.deepEqual(result.verificationCommands, [
    "node --test",
    "node scripts/verify-owner.js",
    "node scripts/check-scope.js",
  ]);
  assert.notEqual(result.verificationCommands, patchState.verificationCommands);
  assert.equal(result.riskOwner, "worker.long-autonomous");
  assert.equal(result.patchSummary, "owner seam patched");
});
