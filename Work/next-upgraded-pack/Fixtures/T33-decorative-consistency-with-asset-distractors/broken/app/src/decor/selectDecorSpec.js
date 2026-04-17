function selectDecorSpec({ tone, assetCatalog }) {
  const accentToken = `accent-${tone}`;
  const assetPath = assetCatalog.legacy[`${tone}Ring`] ?? assetCatalog.drafts[`${tone}Ring`] ?? assetCatalog.real[`${tone}Ring`];

  return {
    tone,
    accentToken,
    assetPath,
  };
}

module.exports = {
  selectDecorSpec,
};
