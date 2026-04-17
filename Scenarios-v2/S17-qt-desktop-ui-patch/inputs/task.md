# Task

You are acting as `$qt-ui-engineer` on an admitted `P05` specialty implementation phase.

## Goal

Repair the bundle-local Qt rename dialog in `candidate/qt-settings-dialog/` so its focus order,
keyboard behavior, and reuse lifecycle match the accepted desktop interaction contract without
widening into non-Qt surfaces.

## Required output

Update these files only:

- `candidate/qt-settings-dialog/src/qt_settings_dialog/rename_preset_dialog.py`
- `candidate/qt-settings-dialog/tests/test_rename_preset_dialog.py`

## Qt UI requirements

- the dialog must place initial focus on `name_edit`
- the validation error label must stay non-focusable and out of the tab order
- the tab chain must be `name_edit -> pin_checkbox -> save_button -> cancel_button`
- blank or whitespace-only names must disable `Save`, show the error label, and recover focus back
  to `name_edit` if `Save` loses eligibility while focused
- `Return` / `Enter` may accept only when the dialog is currently valid
- `Escape` must reject the dialog
- `prepare_for_reopen(...)` must reset prior accept or reject state, hide stale error UI, reapply
  validation for the new suggestion, and restore focus to `name_edit`

## Disallowed behavior

- do not edit `inputs/`, `oracle/`, or `verifiers/`
- do not introduce browser, HTML, DOM, or Playwright-style solutions
- do not move the fix into model/view infrastructure, geometry helpers, or external harness code
- do not "solve" the scenario by weakening the direct test coverage only
