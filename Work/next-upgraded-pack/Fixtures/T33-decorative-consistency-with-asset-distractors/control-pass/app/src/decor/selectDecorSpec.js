function selectDecorSpec({ tone, assetCatalog }) {
  const accentByTone = {
    warning: "accent-amber",
    success: "accent-green",
    note: "accent-blue",
  };
  const assetPath = assetCatalog.real[`${tone}Ring`];

  return {
    tone,
    accentToken: accentByTone[tone],
    assetPath,
  };
}

module.exports = {
  selectDecorSpec,
};
