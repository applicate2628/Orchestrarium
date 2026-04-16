function dedupe(list) {
  return Array.from(new Set(list));
}

function addProviderLocalNotePreview(preferredSlots, providerLocalNote) {
  if (!providerLocalNote || preferredSlots.includes(providerLocalNote)) {
    return preferredSlots;
  }

  return [...preferredSlots, providerLocalNote];
}

function mergeLaneVerdict(base, update) {
  const providerLocalNote =
    update.provider_local_note !== undefined
      ? update.provider_local_note
      : base.provider_local_note;

  const preferredSlots = dedupe([
    ...(Array.isArray(base.preferred_slots) ? base.preferred_slots : []),
    ...(Array.isArray(update.preferred_slots) ? update.preferred_slots : []),
  ]).filter(Boolean);

  return {
    lane: update.lane || base.lane,
    preferred_slots: addProviderLocalNotePreview(preferredSlots, providerLocalNote),
    provider_local_note: providerLocalNote || null,
    ui_label: update.ui_label || base.ui_label || null,
    confidence: update.confidence || base.confidence || "medium",
  };
}

module.exports = {
  mergeLaneVerdict,
};
