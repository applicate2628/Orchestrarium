# Selected Copilot workspace registration lifecycle

This Windows-only helper manages one dedicated file:
`.github/hooks/orchestrarium.json`. It reuses the existing installer transaction
and path writer. It does not copy shared Lead, change receipts, add an installer
CLIENTS entry, change settings, or qualify native Copilot activation.

## Preview and apply

Use the supplied Python or another supported Python 3.13+:

```text
python scripts/installation/copilot_registration.py --project PROJECT --desired NEW.json
python scripts/installation/copilot_registration.py --project PROJECT --desired NEW.json --apply
```

Without --apply the existing writer runs in dry-run mode. It does not publish the
registration. The desired document must contain exactly one preToolUse command
handler and only the supported version/hooks frame. Prepare its command using
the existing transport formatter and qualified runtime/script paths; this helper
does not install those dependencies or validate their native host compatibility.

An identical file is a no-op. Updating a different existing file requires its
exact explicitly selected prior document:

```text
python scripts/installation/copilot_registration.py --project PROJECT --desired NEW.json --previous OLD.json --apply
python scripts/installation/copilot_registration.py --project PROJECT --remove --previous OLD.json --apply
```

OLD.json is deliberate current-byte selection, not inferred historical ownership
or a generated permission receipt. Keep that selection independent of the target;
do not automatically read an unknown file and claim it was approved for replacement.
Changed bytes, duplicate fields, mixed handlers and unexpected structure refuse.
Other hook files remain untouched. This is not handler-level merging.

Before a successful update/removal, exact previous content is preserved in a
unique file under PROJECT/trash, outside hook discovery. The JSON result reports
that path. Removal is registration-only; shared runtime and dependencies remain.
The retained copy preserves bytes, not a guarantee of original security metadata.

## Boundaries and receiving

The established physical owner rejects linked ancestry and uses its existing
snapshot/recovery protocol. Apply rechecks the selected bytes after acquisition.
Tests cover real Windows create/no-op/update/removal, foreign sibling preservation,
preview, junction refusal and injected update/removal failure rollback. They are
not concurrent adversarial-race or crash-atomicity qualification. Existing POSIX
effect restrictions remain unchanged.

Writing this file can make a hook discoverable by a running supported host.
Review command and source duplication before using --apply in a real project.
No model, host session or live configuration was used for isolated acceptance.
The official timeout, trust and dispatch limitations in
[the transport boundary](copilot-transport-boundary.md) still apply.
