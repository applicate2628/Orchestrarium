# Triage notes

- `styles.css` is the only stylesheet linked by `screen.html`.
- `components/panel.css` looks tempting because it already contains the intended inline fix, but it is not loaded.
- `components/legacy-panel.css` is retained as historical reference and is also not loaded.
- A valid fix must preserve the active chip color token while correcting note placement and collapsed-state behavior.
