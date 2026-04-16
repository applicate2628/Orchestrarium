function mergeLaneVerdict(base, update) {
  return {
    lane: update.lane || base.lane,
    preferred_slots: Array.isArray(update.preferred_slots) ? update.preferred_slots : base.preferred_slots,
    provider_local_note: update.provider_local_note || base.provider_local_note || null,
  };
}

module.exports = {
  mergeLaneVerdict,
};
