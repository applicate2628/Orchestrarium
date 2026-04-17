function selectDecorSpec(assetCatalog, tone) {
  return assetCatalog.legacy[`${tone}Ring`] ?? assetCatalog.drafts[`${tone}Ring`] ?? assetCatalog.real[`${tone}Ring`];
}

module.exports = {
  selectDecorSpec,
};
