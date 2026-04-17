const { selectDecorSpec } = require("./decor/selectDecorSpec");

function runDecorationPreview({ tone, assetCatalog }) {
  return selectDecorSpec({ tone, assetCatalog });
}

module.exports = {
  runDecorationPreview,
};
