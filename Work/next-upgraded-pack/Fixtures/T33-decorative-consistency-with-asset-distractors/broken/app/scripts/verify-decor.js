const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

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

function read(relativePath) {
  return fs.readFileSync(path.join(__dirname, "..", relativePath), "utf8");
}

try {
  assert.deepEqual(runDecorationPreview({ tone: "warning", assetCatalog }), {
    tone: "warning",
    accentToken: "accent-amber",
    assetPath: "assets/icons/warning-ring.svg",
  });
  assert.deepEqual(runDecorationPreview({ tone: "success", assetCatalog }), {
    tone: "success",
    accentToken: "accent-green",
    assetPath: "assets/icons/success-ring.svg",
  });
  assert.deepEqual(runDecorationPreview({ tone: "note", assetCatalog }), {
    tone: "note",
    accentToken: "accent-blue",
    assetPath: "assets/icons/note-ring.svg",
  });

  assert.match(read("components/badge.css"), /decor preview only/);
  assert.match(read("styles.css"), /real owner seam is selectDecorSpec/);
  assert.match(read("assets/legacy/warning-ring.svg"), /legacy-warning-ring/);
  assert.match(read("assets/drafts/warning-ring.svg"), /draft-warning-ring/);

  console.log("VERIFY_T33_DECOR_OK");
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
