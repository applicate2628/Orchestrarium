# State Failure Ledger

| Symptom | Expected owner |
|---|---|
| edits disappear after tab switch | `editor-state.mjs` dirty baseline tracking |
| failed save shows success | `editor-state.mjs` save result handling |
| invalid slug commits to baseline | `editor-state.mjs` validation and save gating |
| screen reader hears no status update | `editor-panel.mjs` status rendering |
| long labels overflow footer buttons | `editor.css` layout constraints |
