# UI State Contract

The repaired board must satisfy the following state-specific expectations.

## Loading

- render a dedicated loading message that includes `Loading release checks...`
- announce the message through a polite live region
- keep the board scoped to loading feedback rather than stale result cards

## Success

- render filter controls as buttons, not generic containers
- mark the active filter with `aria-pressed="true"`
- include a summary with the exact form `Showing N checks`
- tie the result list to that summary with `aria-describedby="board-summary"`
- keep the success list visible only when there are matching checks

## Empty

- render the heading `No checks match this filter`
- mention the selected filter label in the explanatory copy
- expose a reset action labeled `Reset to all checks`

## Error

- announce the failure through an element with `role="alert"`
- use retry copy labeled `Retry checks`
- hide stale success cards while the error message is shown
