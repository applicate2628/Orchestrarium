function mergeLaneVerdictLegacy(base, update) {
  return {
    lane: update.lane || base.lane,
    provider_local_note: update.provider_local_note || base.provider_local_note || null,
    preferred_slots: base.preferred_slots,
  };
}

module.exports = {
  mergeLaneVerdictLegacy,
};
