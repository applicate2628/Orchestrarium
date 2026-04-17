const test = require("node:test");
const assert = require("node:assert/strict");

const { runDecorationPreview } = require("../src/runDecorationPreview");

const assetCatalog = {
  real: {
    warningRing: "assets/icons/warning-ring.svg",
    successRing: "assets/icons/success-ring.svg",
    noteRing: "assets/icons/note-ring.svg",
  },
  legacy: {
    warningRing: "assets/legacy/warning-ring.svg",
    successRing: "assets/legacy/success-ring.svg",
    noteRing: "assets/legacy/note-ring.svg",
  },
  drafts: {
    warningRing: "assets/drafts/warning-ring.svg",
    successRing: "assets/drafts/success-ring.svg",
    noteRing: "assets/drafts/note-ring.svg",
  },
};

test("warning tone keeps the curated amber accent and real icon asset together", () => {
  const result = runDecorationPreview({ tone: "warning", assetCatalog });
  assert.equal(result.accentToken, "accent-amber");
  assert.equal(result.assetPath, "assets/icons/warning-ring.svg");
});

test("success tone keeps the curated green accent and real icon asset together", () => {
  const result = runDecorationPreview({ tone: "success", assetCatalog });
  assert.equal(result.accentToken, "accent-green");
  assert.equal(result.assetPath, "assets/icons/success-ring.svg");
});

test("note tone keeps the curated blue accent and real icon asset together", () => {
  const result = runDecorationPreview({ tone: "note", assetCatalog });
  assert.equal(result.accentToken, "accent-blue");
  assert.equal(result.assetPath, "assets/icons/note-ring.svg");
});
