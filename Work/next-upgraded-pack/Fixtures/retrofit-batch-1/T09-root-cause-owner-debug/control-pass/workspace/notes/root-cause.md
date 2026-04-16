owner seam
- `workspace/src/providers/mergeLaneVerdict.js`

failure mechanism
- `mergeLaneVerdict` still injects `provider_local_note` into `preferred_slots` via `addProviderLocalNotePreview`.

do not patch
- `workspace/src/ui/mergeLaneVerdict.js`
- `workspace/logs/failure.log`
- `workspace/test/failure-context.txt`
