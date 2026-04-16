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

function verifyRootCauseNote() {
  const note = read("../notes/root-cause.md");

  assert.match(note, /^owner seam\r?\n- `workspace\/src\/providers\/mergeLaneVerdict\.js`/m);
  assert.match(note, /^failure mechanism\r?\n- `mergeLaneVerdict` still injects `provider_local_note` into `preferred_slots` via `addProviderLocalNotePreview`\./m);
  assert.match(note, /^do not patch\r?\n- `workspace\/src\/ui\/mergeLaneVerdict\.js`\r?\n- `workspace\/logs\/failure\.log`\r?\n- `workspace\/test\/failure-context\.txt`/m);
}

try {
  verifyScenario({
    base: {
      lane: "worker.systems-implementation",
      preferred_slots: ["claude", "codex", "gemini"],
      provider_local_note: null,
      ui_label: "Systems patch lane",
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
      lane: "worker.toolchain-root-ownership",
      preferred_slots: ["codex", "lab-shadow-runner"],
      provider_local_note: null,
      ui_label: "Toolchain owner lane",
      confidence: "medium",
    },
    update: {
      preferred_slots: ["claude", "lab-shadow-runner"],
      provider_local_note: "lab-shadow-runner-note",
    },
    expectedSlots: ["codex", "lab-shadow-runner", "claude"],
    expectedNote: "lab-shadow-runner-note",
  });

  verifyRootCauseNote();
  assert.equal(read("../src/ui/mergeLaneVerdict.js"), expectedUiMergePreview);
  assert.equal(read("../src/ui/renderLocalNote.js"), expectedRenderLocalNote);
  assert.equal(read("../../docs/project-mirror/src/providers/mergeLaneVerdict.js"), expectedDocsMirror);
  assert.equal(read("../../legacy/project-copy/src/providers/mergeLaneVerdict.js"), expectedLegacyMirror);

  console.log("VERIFY_T09_OWNER_OK");
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
