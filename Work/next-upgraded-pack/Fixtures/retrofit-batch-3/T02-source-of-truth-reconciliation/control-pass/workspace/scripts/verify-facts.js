const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function readJson(relativePath) {
  return JSON.parse(fs.readFileSync(path.join(__dirname, "..", relativePath), "utf8"));
}

function read(relativePath) {
  return fs.readFileSync(path.join(__dirname, "..", relativePath), "utf8");
}

try {
  const answer = readJson("out/facts.json");

  assert.deepEqual(answer, {
    archiveSurface: "frozen-historical",
    mutableSurface: "work-next-upgraded-pack",
    archiveX3Label: "opus 4.6max",
    mutableX3Label: "opus 4.7max",
    rewriteArchive: false,
    currentDefaultSource: "short-results-current-2026-04-17",
  });

  const source = read("inputs/source-excerpt.md");
  assert.match(source, /frozen historical evidence/);
  assert.match(source, /the historical archive label for `X3` remains `opus 4\.6max`/);
  assert.match(source, /the current mutable label for `X3` is `opus 4\.7max`/);

  console.log("VERIFY_T02_FACTS_OK");
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
