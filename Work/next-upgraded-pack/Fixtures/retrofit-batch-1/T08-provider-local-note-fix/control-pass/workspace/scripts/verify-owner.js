const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");

const { mergeLaneVerdict } = require("../src/providers/mergeLaneVerdict");

const expectedUiMergePreview = `function mergeLaneVerdictUiPreview(note) {
  return note ? \`Local note: \${note}\` : "No local note";
}

module.exports = {
  mergeLaneVerdictUiPreview,
};
`;

const expectedRenderLocalNote = `function renderLocalNote(note) {
  return note ? \`<span class="provider-local-note">\${note}</span>\` : "";
}

module.exports = {
  renderLocalNote,
};
`;

const expectedDocsMirror = `function mergeLaneVerdict(base, update) {
  return {
    lane: update.lane || base.lane,
    preferred_slots: Array.isArray(update.preferred_slots) ? update.preferred_slots : base.preferred_slots,
    provider_local_note: update.provider_local_note || base.provider_local_note || null,
  };
}

module.exports = {
  mergeLaneVerdict,
};
`;

const expectedLegacyMirror = `function mergeLaneVerdictLegacy(base, update) {
  return {
    lane: update.lane || base.lane,
    provider_local_note: update.provider_local_note || base.provider_local_note || null,
    preferred_slots: base.preferred_slots,
  };
}

module.exports = {
  mergeLaneVerdictLegacy,
};
`;

function read(relativePath) {
  return fs.readFileSync(path.join(__dirname, relativePath), "utf8");
}

function verifyScenario({ base, update, expectedSlots, expectedNote }) {
  const merged = mergeLaneVerdict(base, update);

  assert.deepEqual(merged.preferred_slots, expectedSlots);
  assert.equal(merged.provider_local_note, expectedNote);
}

try {
  verifyScenario({
    base: {
      lane: "advisory.security-transport",
      preferred_slots: ["claude", "codex", "gemini"],
      provider_local_note: null,
      ui_label: "Security review",
      confidence: "medium",
    },
    update: {
      provider_local_note: "x4-secret-fallback",
      confidence: "high",
    },
    expectedSlots: ["claude", "codex", "gemini"],
    expectedNote: "x4-secret-fallback",
  });

  verifyScenario({
    base: {
      lane: "worker.ui-implementation",
      preferred_slots: ["claude", "codex"],
      provider_local_note: null,
      ui_label: "UI patch lane",
      confidence: "medium",
    },
    update: {
      preferred_slots: ["gemini", "claude"],
      provider_local_note: "x6-shadow-lab",
    },
    expectedSlots: ["claude", "codex", "gemini"],
    expectedNote: "x6-shadow-lab",
  });

  verifyScenario({
    base: {
      lane: "worker.systems-implementation",
      preferred_slots: ["gemini"],
      provider_local_note: null,
      ui_label: "Systems lane",
      confidence: "medium",
    },
    update: {
      preferred_slots: ["codex", "gemini"],
      provider_local_note: "provider-local-2026",
      ui_label: "Systems lane",
    },
    expectedSlots: ["gemini", "codex"],
    expectedNote: "provider-local-2026",
  });

  assert.equal(read("../src/ui/mergeLaneVerdict.js"), expectedUiMergePreview);
  assert.equal(read("../src/ui/renderLocalNote.js"), expectedRenderLocalNote);
  assert.equal(read("../../docs/project-mirror/src/providers/mergeLaneVerdict.js"), expectedDocsMirror);
  assert.equal(read("../../legacy/project-copy/src/providers/mergeLaneVerdict.js"), expectedLegacyMirror);

  console.log("VERIFY_T08_OWNER_OK");
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
