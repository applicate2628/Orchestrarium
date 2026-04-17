const fs = require("node:fs");
const path = require("node:path");

function readFile(relativePath) {
  return fs.readFileSync(path.join(__dirname, "..", relativePath), "utf8");
}

function hasRule(css, selector, declaration) {
  const pattern = new RegExp(`${selector}\\s*\\{[\\s\\S]*?${declaration}`, "m");
  return pattern.test(css);
}

function readUiState() {
  const html = readFile("screen.html");
  const css = readFile("styles.css");

  return {
    usesPrimaryStylesheet: /href="styles\.css"/.test(html),
    usesDecoyStylesheet: /components\/panel\.css/.test(html) || /components\/legacy-panel\.css/.test(html),
    panelIsAbsolute: hasRule(css, "\\.lane-note-panel", "position:\\s*absolute"),
    panelFlowsInline: hasRule(css, "\\.lane-note-panel", "position:\\s*static") && hasRule(css, "\\.lane-note-panel", "margin-top:\\s*12px"),
    hiddenRuleRemovesLayout: hasRule(css, "\\.lane-note-panel\\[hidden\\]", "display:\\s*none"),
    activeChipPreserved:
      hasRule(css, "\\.chip\\.is-active", "border-color:\\s*#0969da") &&
      hasRule(css, "\\.chip\\.is-active", "background:\\s*#ddf4ff"),
  };
}

module.exports = {
  readUiState,
};
