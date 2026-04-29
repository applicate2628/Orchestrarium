# N88 UX Runtime Event-Policy Simulator

This diagnostic `E78` scenario tests whether UX structure work can be made executable. The
candidate does not build UI code. It defines UX-owned runtime, breakpoint, and re-entry policies;
the verifier replays hidden traces against those policies.

The hidden simulator checks dominant actions, publish suppression, disabled reasons, scoped export
behavior, follow-up re-entry cues, and breakpoint ordering. Phrase-only JSON is not enough: the
policy must evaluate hidden traces consistently.
