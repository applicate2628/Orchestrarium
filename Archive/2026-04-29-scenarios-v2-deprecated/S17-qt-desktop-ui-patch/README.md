# S17 Qt Desktop UI Patch

`S17` benchmarks `R17 $qt-ui-engineer` on a bounded Qt Widgets dialog repair. The scored task is to
correct focus order, keyboard behavior, and dialog reuse lifecycle in a bundle-local desktop UI
module without drifting into browser flows, model/view plumbing, geometry logic, or scorer edits.

## Scenario summary

The mutable candidate root contains a small rename dialog expressed in Qt-Widgets-style Python.
Its start state is intentionally wrong in ways that matter for desktop keyboard use:

- the validation error label is focusable even though it should stay out of the tab chain
- the tab order routes through `Cancel` before the checkbox and `Save`
- blank input disables `Save` but leaves keyboard focus stranded on the disabled button
- `Return` accepts the dialog even when the current input is invalid
- reusing the same dialog instance does not reset result state or restore focus to the name field

The fix must stay inside the dialog module and its direct verification file only.

## Expected candidate work

Edit only the files listed in `scenario.yaml`:

- `candidate/qt-settings-dialog/src/qt_settings_dialog/rename_preset_dialog.py`
- `candidate/qt-settings-dialog/tests/test_rename_preset_dialog.py`

Use the immutable packet in `inputs/` to preserve the intended Qt focus contract, keyboard
expectations, and non-browser boundary. The expected local validation flow after a repair is:

1. run `python tests/test_rename_preset_dialog.py` from `candidate/qt-settings-dialog/`
2. run `python verifiers/run_qt_ui_checks.py` from the bundle root
3. use `python verifiers/check_scope.py --changed-path ...` to confirm the diff stayed in bounds

## What this bundle tests

- Qt Widgets focus policy discipline instead of generic web accessibility language
- keyboard and dialog-button behavior in a desktop modal flow
- widget lifecycle handling when a dialog instance is reused
- scope control for a specialty implementation bundle

## Bundle map

- `inputs/` holds the immutable task contract, focus and keyboard requirements, lifecycle notes,
  and the explicit non-browser boundary
- `candidate/` is the mutable run root copied for each execution
- `oracle/` defines the bundle contract, interaction truth, prohibited shortcuts, and scoring
  anchors
- `verifiers/` contains bundle-shape, start-state, completed-run, and scope checks
