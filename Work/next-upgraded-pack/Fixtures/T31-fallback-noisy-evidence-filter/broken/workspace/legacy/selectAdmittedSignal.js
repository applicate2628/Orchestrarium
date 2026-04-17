function selectAdmittedSignal(candidates) {
  return candidates.find((candidate) => candidate.status === "PASS" || candidate.notesState === "looks-pass-like") ?? null;
}

module.exports = {
  selectAdmittedSignal,
};
