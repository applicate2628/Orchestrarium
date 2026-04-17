const { selectAdmittedSignal } = require("./fallback/selectAdmittedSignal");

function runFallbackReview({ candidates }) {
  const winner = selectAdmittedSignal({ candidates });
  if (!winner) {
    return {
      selectedRowId: null,
      selectedSource: null,
      overlayDecision: "no-admission",
    };
  }

  return {
    selectedRowId: winner.rowId,
    selectedSource: winner.source,
    overlayDecision: winner.overlayLevel,
  };
}

module.exports = {
  runFallbackReview,
};
