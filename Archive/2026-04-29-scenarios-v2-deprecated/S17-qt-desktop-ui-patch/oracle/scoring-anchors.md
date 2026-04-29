# Scoring Anchors

`S17` uses the `implementation` score profile.

## Strong pass signals

- the dialog stays in the bundle-local Qt widget seam and direct tests only
- the validation label is non-focusable and absent from the tab chain
- the tab order matches the accepted desktop sequence exactly
- blank input disables `Save`, shows the error, and recovers focus to `name_edit`
- `Return` only accepts a valid dialog, `Escape` rejects, and dialog reuse clears stale result
  state before restoring focus to the editor

## Common failure signals

- the fix uses browser, DOM, or generic web accessibility language instead of Qt widget behavior
- `Cancel` stays ahead of the checkbox or `Save` in the tab chain
- the dialog still accepts invalid `Return` presses or keeps focus parked on a disabled button
- reopening the dialog preserves prior result flags or fails to restore the edit field focus
- the candidate widens outside the allowed dialog module and direct verification file
