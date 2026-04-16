function renderLocalNote(note) {
  return note ? `<span class="provider-local-note">${note}</span>` : "";
}

module.exports = {
  renderLocalNote,
};
