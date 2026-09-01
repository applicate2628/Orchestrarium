# Product Brief - CSV Export Of Results

## Problem Statement

Operators need to take the results they are currently looking at out of the tool. The accepted problem
is to add a CSV export of the currently-visible result rows to the existing results table. This brief
covers that CSV export and nothing broader; the intake raised several adjacent asks that are parked below.

## In Scope

- CSV export of the currently-visible result rows.
- A download button in the results toolbar that triggers the export.
- The export reflects the current filter and sort of the table, so what is exported matches what is shown.

## Out Of Scope (Parked)

These came up in the noisy intake but are out of scope for this brief. They are parked with a reason so
they are neither silently dropped nor pulled into this effort:

- Additional export formats (XLSX, PDF) - parked; a separate format-support effort with its own design.
- Scheduled / email export - parked; that is a new delivery channel, not a change to this table.
- A reporting dashboard with charts - parked; that is a different product surface entirely.

## Success Criteria

- Clicking the toolbar download button exports exactly the currently-visible rows as a valid CSV that
  honors the active filter and sort.

## Gate Decision

PASS
