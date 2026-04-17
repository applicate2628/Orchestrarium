# Evidence E1 - System Overview

All names and identifiers in this scenario are synthetic.

## Proposed `relay-and-export` flow

```text
Operator workstation
  -> runner-orchestrator
      -> scenario bundle reader
      -> credential broker
      -> provider launcher
          -> external provider CLI / service
      -> raw evidence vault
      -> analyst export packager
```

## Components and responsibilities

| Component | Role | Data handled |
|---|---|---|
| operator workstation | starts runs and approves export | scenario ID, run manifest, analyst destination |
| runner-orchestrator | owns run state and staging | scenario files, attachment manifest, hashes, logs |
| credential broker | mints short-lived secrets | provider session token, vault write token |
| provider launcher | invokes external provider CLI | prompt packet, selected attachments, provider output |
| raw evidence vault | restricted storage for raw run artifacts | raw stdout, raw stderr, structured result packet |
| analyst export packager | creates sanitized handoff | redacted summary, selected excerpts, provenance record |

## Intended flow notes

- the runner reads scenario material from the repo worktree and stages selected files for upload
- the provider launcher writes debug capture to `run-debug.json`
- raw provider output is preserved for later audit in the evidence vault
- analysts should receive a redacted package, not the raw vault contents
- publication outside the analyst export path is out of scope for this design draft
