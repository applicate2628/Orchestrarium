# Browser Checklist

Use this checklist when inspecting the bundle-local preview in a real browser.

## Preview route

1. From `candidate/workspace/`, run `node scripts/static-server.mjs`.
2. Open `http://127.0.0.1:4173`.
3. Use the preview-state and active-filter control bars to inspect each board state.

## Expected browser behavior after the patch

- loading announces `Loading release checks...` through a polite live region
- success shows filter buttons with a visible active state and summary text `Showing N checks`
- choosing `Blocked` produces the empty state with `No checks match this filter`
- the empty state offers a visible `Reset to all checks` action
- the error state announces the failure and hides stale check cards
- keyboard focus is visibly distinct on filter controls, reset, and retry actions
