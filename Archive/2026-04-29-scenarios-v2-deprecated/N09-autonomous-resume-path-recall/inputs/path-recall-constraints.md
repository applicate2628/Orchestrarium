# Path Recall Constraints

The correct implementation must:

- normalize Windows and POSIX separators
- preserve `previousRoot` when it is still valid
- avoid choosing docs or legacy mirrors just because they were edited recently
- still support alternate real roots such as `packages/editor-app`
