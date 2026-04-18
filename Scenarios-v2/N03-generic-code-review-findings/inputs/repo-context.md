# Repo Context Memo

## Relevant boundaries

| Surface | Owner | Review implication |
|---|---|---|
| `src/review_packet_builder.py` | bundle-local generic review tooling | same-owner helper; review it for correctness and contract fit |
| changed-path list | reviewer evidence packet | must preserve all touched files the reviewer needs to inspect |
| finding fingerprints | local dedupe helper | stable local identifiers only; not an auth or secret boundary |
| hunk parsing | evidence extraction | malformed input must stay diagnosable |

## Local standards that matter here

- generic review packets stay findings-only and keep full changed-path context
- diff evidence should remain debuggable; silent empty fallbacks hide reviewable risk
- this packet is capped at `12` changed paths per run, so small local loops are acceptable here
- the admitted work does not introduce a new service boundary, secret surface, or hard performance
  budget

## Non-issues for this scenario

- a bundle-local dataclass is acceptable when it stays in the same module owner
- `sha1` is used only for short deterministic local fingerprints, not for trust or auth decisions
- small fixed limits and single-pass list processing are not separate performance findings here
