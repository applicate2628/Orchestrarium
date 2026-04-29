# Task

Fix the helper that recalls the workspace root after a later follow-up edit.

The helper must prefer the previously accepted root when it is still a valid manifest root. Only if
that root is unavailable should it use the current start directory or prior edit evidence.
