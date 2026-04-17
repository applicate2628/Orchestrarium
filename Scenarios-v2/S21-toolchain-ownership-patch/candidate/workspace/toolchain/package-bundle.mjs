import { readFileSync } from "node:fs";

const readJson = (relativePath) =>
  JSON.parse(readFileSync(new URL(relativePath, import.meta.url), "utf8"));

const workspaceManifest = readJson("../package.json");
const bundlePlan = readJson("./bundle-plan.json");
const packageManifest = readJson("../packages/scenario-bundle/package.json");

const errors = [];

const requireEqual = (actual, expected, message) => {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    errors.push(message);
  }
};

requireEqual(
  workspaceManifest.scripts?.["validate:scenario-bundle"],
  "node toolchain/package-bundle.mjs",
  'package.json script validate:scenario-bundle must equal "node toolchain/package-bundle.mjs"',
);

requireEqual(
  bundlePlan.outDir,
  "dist",
  'bundle-plan.json outDir must equal "dist"',
);

requireEqual(
  bundlePlan.publishFiles,
  ["dist/**", "README.md"],
  'bundle-plan.json publishFiles must equal ["dist/**", "README.md"]',
);

requireEqual(
  bundlePlan.entrypoints,
  {
    ".": "src/index.js",
    "./cli": "src/cli.js",
  },
  "bundle-plan.json entrypoints must stay rooted at src/index.js and src/cli.js",
);

requireEqual(
  packageManifest.main,
  "./dist/index.js",
  'package manifest main must equal "./dist/index.js"',
);

requireEqual(
  packageManifest.bin?.["scenario-bundle"],
  "./dist/cli.js",
  'package manifest bin.scenario-bundle must equal "./dist/cli.js"',
);

requireEqual(
  packageManifest.exports,
  {
    ".": "./dist/index.js",
    "./cli": "./dist/cli.js",
  },
  "package manifest exports must point to dist outputs",
);

requireEqual(
  packageManifest.files,
  ["dist", "README.md"],
  'package manifest files must equal ["dist", "README.md"]',
);

const editableBlob = JSON.stringify({
  workspaceManifest,
  bundlePlan,
  packageManifest,
});

for (const token of ["T29", "run-active-cohort-batch.ps1"]) {
  if (editableBlob.includes(token)) {
    errors.push("editable toolchain files must not reference legacy runner or T29 fixtures");
    break;
  }
}

if (errors.length > 0) {
  console.error("S21 validation failed:");
  for (const error of errors) {
    console.error(`- ${error}`);
  }
  process.exit(1);
}

console.log("S21 validation PASS");
