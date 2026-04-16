function mergeLaneVerdictUiPreview(note) {
  return note ? `Local note: ${note}` : "No local note";
}

module.exports = {
  mergeLaneVerdictUiPreview,
};
