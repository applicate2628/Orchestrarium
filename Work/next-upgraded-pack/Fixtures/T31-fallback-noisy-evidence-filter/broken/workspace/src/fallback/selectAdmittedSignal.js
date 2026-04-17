function selectAdmittedSignal({ candidates }) {
  for (const candidate of candidates) {
    if (candidate.status === "PASS" || candidate.notesState === "looks-pass-like") {
      return candidate;
    }
  }

  return candidates[0] ?? null;
}

module.exports = {
  selectAdmittedSignal,
};
