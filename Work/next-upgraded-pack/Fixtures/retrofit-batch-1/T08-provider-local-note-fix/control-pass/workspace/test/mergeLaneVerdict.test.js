const test = require("node:test");
const assert = require("node:assert/strict");

const { mergeLaneVerdict } = require("../src/providers/mergeLaneVerdict");

test("keeps provider-local note out of preferred provider slots", () => {
  const merged = mergeLaneVerdict(
    {
      lane: "advisory.security-transport",
      preferred_slots: ["claude", "codex", "gemini"],
      provider_local_note: null,
      ui_label: "Security review",
      confidence: "medium",
    },
    {
      provider_local_note: "x4-secret-fallback",
      confidence: "high",
    }
  );

  assert.deepEqual(merged.preferred_slots, ["claude", "codex", "gemini"]);
  assert.equal(merged.provider_local_note, "x4-secret-fallback");
  assert.equal(merged.ui_label, "Security review");
  assert.equal(merged.confidence, "high");
});

test("dedupes explicit provider slots while keeping provider-local note separate", () => {
  const merged = mergeLaneVerdict(
    {
      lane: "worker.ui-implementation",
      preferred_slots: ["claude", "codex"],
      provider_local_note: null,
      ui_label: "UI patch lane",
      confidence: "medium",
    },
    {
      preferred_slots: ["gemini", "claude"],
      provider_local_note: "x6-shadow-lab",
    }
  );

  assert.deepEqual(merged.preferred_slots, ["claude", "codex", "gemini"]);
  assert.equal(merged.provider_local_note, "x6-shadow-lab");
  assert.equal(merged.ui_label, "UI patch lane");
});
