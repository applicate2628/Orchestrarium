# Triage notes

- A teammate suggested setting `z-index: 9999` and leaving everything else unchanged.
- Another suggestion was to turn the note into a full-screen modal so the focus story becomes easier.
- Platform guidance for this benchmark still forbids a whole-layout redesign; keep the table and per-row note structure.
- The desired fix should work for both web and Qt-style UI reasoning lanes, so prefer structural ownership fixes over browser-only workarounds.
