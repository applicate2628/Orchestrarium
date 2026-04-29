# Task

Fix the build-owner continuity flow inside the real nested workspace.

The worker must:

- find the owning source file under `candidate/workspace/src/**`
- find the real workspace root from the current start directory
- keep both linked fixes in the same owner boundary
- leave all decoys unchanged
- run both local validation commands
