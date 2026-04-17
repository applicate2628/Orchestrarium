# False-Positive Traps

Do not raise these as standalone accessibility findings in `S29`:

- `role="dialog"` with `aria-labelledby="share-title"` is already present; the dialog problem is
  keyboard containment and control semantics, not missing top-level dialog semantics
- the visually hidden `scope-hint` text is valid supporting copy; the defect is the missing
  programmatic state on `scope-toggle`, not the presence of off-screen helper text
- `Escape` handling exists and returns focus to the launch button; the blocking issue is the lack of
  `Tab` and `Shift+Tab` containment while the dialog is open
- this review does not require a browser overlay, screenshot baseline, or visual diff harness; the
  provided source and recorded observations are the intended evidence packet
- the report should stay an accessibility gate; converting it into a QA acceptance matrix or a code
  patch request is scope drift, not a finding
