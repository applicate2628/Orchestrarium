function selectAdmittedSignal(candidateList) {
  return candidateList.find((candidate) => candidate.status === "PASS" || candidate.notesState === "looks-pass-like") ?? null;
}

module.exports = {
  selectAdmittedSignal,
};
