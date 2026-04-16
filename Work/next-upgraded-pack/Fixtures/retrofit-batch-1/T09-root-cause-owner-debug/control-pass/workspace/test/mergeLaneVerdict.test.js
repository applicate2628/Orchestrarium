const test = require("node:test");
const assert = require("node:assert/strict");

const { mergeLaneVerdict } = require("../src/providers/mergeLaneVerdict");

test("keeps provider-local note out of preferred provider slots", () => {
  const merged = mergeLaneVerdict(
    {
      lane: "worker.systems-implementation",
      preferred_slots: ["claude", "codex", "gemini"],
      provider_local_note: null,
      ui_label: "Systems patch lane",
      confidence: "medium",
    },
    {
      provider_local_note: "x4-secret-fallback",
      confidence: "high",
    }
  );

  assert.deepEqual(merged.preferred_slots, ["claude", "codex", "gemini"]);
  assert.equal(merged.provider_local_note, "x4-secret-fallback");
  assert.equal(merged.ui_label, "Systems patch lane");
  assert.equal(merged.confidence, "high");
});

test("keeps explicit custom provider slots instead of over-filtering", () => {
  const merged = mergeLaneVerdict(
    {
      lane: "worker.toolchain-root-ownership",
      preferred_slots: ["codex", "lab-shadow-runner"],
      provider_local_note: null,
      ui_label: "Toolchain owner lane",
      confidence: "medium",
    },
    {
      preferred_slots: ["claude", "lab-shadow-runner"],
      provider_local_note: "lab-shadow-runner-note",
    }
  );

  assert.deepEqual(merged.preferred_slots, ["codex", "lab-shadow-runner", "claude"]);
  assert.equal(merged.provider_local_note, "lab-shadow-runner-note");
  assert.equal(merged.ui_label, "Toolchain owner lane");
});
