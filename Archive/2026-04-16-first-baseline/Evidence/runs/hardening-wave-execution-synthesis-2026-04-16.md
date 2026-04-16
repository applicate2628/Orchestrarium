Date: 2026-04-16
Owner: `$lead`
Status: `PASS`

## Purpose

Canonize the first complete hardening-wave execution set for:

- `G16` toolchain-owner ambiguity
- `G17` late-session path recall
- `G18` reviewer-to-worker transition

across the four non-Gemini comparison rows:

- `X1`
- `X2`
- `X3`
- `X4`

## Evidence basis

| Target | Capture basis |
|---|---|
| `X1` | fresh reruns for `G16` and `G18`, plus raw-green canonization for `G17` |
| `X2` | raw-green canonization from existing scratch evidence for `G16..G18` |
| `X3` | fresh first admitted runs for `G16..G18` |
| `X4` | raw-green canonization from existing scratch evidence for `G16..G18` |

## Verdict grid

| Probe | `X1` | `X2` | `X3` | `X4` |
|---|---|---|---|---|
| `G16` | `PASS` | `PASS` | `PASS` | `PASS` |
| `G17` | `PASS` | `PASS` | `PASS` | `PASS` |
| `G18` | `PASS` | `PASS` | `PASS` | `PASS` |

## Verification contract

| Probe | Verification | `X1` | `X2` | `X3` | `X4` |
|---|---|---|---|---|---|
| `G16` | `npm test` plus `node scripts/verify-toolchain-owner.js` | `PASS` / `VERIFY_TOOLCHAIN_OWNER_OK` | `PASS` / `VERIFY_TOOLCHAIN_OWNER_OK` | `PASS` / `VERIFY_TOOLCHAIN_OWNER_OK` | `PASS` / `VERIFY_TOOLCHAIN_OWNER_OK` |
| `G17` | `npm test` plus `node scripts/verify-recall.js` | `PASS` / `VERIFY_RECALL_OK` | `PASS` / `VERIFY_RECALL_OK` | `PASS` / `VERIFY_RECALL_OK` | `PASS` / `VERIFY_RECALL_OK` |
| `G18` | `npm test` plus `node scripts/verify-reviewer-worker.js` | `PASS` / `VERIFY_REVIEWER_WORKER_OK` | `PASS` / `VERIFY_REVIEWER_WORKER_OK` | `PASS` / `VERIFY_REVIEWER_WORKER_OK` | `PASS` / `VERIFY_REVIEWER_WORKER_OK` |

## High-signal findings

| Topic | Accepted finding |
|---|---|
| `X2` hardening read | `X2` now has a fully canonized green hardening-wave record on `G16..G18`, which strengthens it as the current strongest bounded fallback-worker path |
| `X4` hardening read | `X4` also clears `G16..G18`, so the harder bounded probes still do not justify demoting it inside the bounded-worker family from these rows alone |
| `X4` boundary | this does **not** erase the later `G15` quality separation; `X4` still stays weaker on messier worker ownership because `G15` fell to brittle exact-path logic |
| `X3` control read | native `X3` stays fully green on the hardening-wave pack, reinforcing that the stronger top path still survives the stricter bounded probes |
| methodology read | `G16..G18` strengthen the benchmark, but they still behave like bounded probes rather than true long-horizon messy-project ownership collapse reproductions |

## Raw output pointers

| Target | Files |
|---|---|
| `X1` | `.scratch/hardening-reruns-2026-04-16/x1-g16.txt`, `.scratch/benchmark-hardening/x1-g17.txt`, `.scratch/hardening-reruns-2026-04-16/x1-g18.txt` |
| `X2` | `.scratch/benchmark-hardening/x2-g16.txt`, `x2-g17.txt`, `x2-g18.txt` |
| `X3` | `.scratch/hardening-reruns-2026-04-16/x3-g16.txt`, `x3-g17.txt`, `x3-g18.txt` |
| `X4` | `.scratch/benchmark-hardening/x4-g16.txt`, `x4-g17.txt`, `x4-g18.txt` |

## Boundary

| Topic | Boundary |
|---|---|
| broad worker trust | passing `G16..G18` does not by itself promote `X2` or `X4` into broad messy-project trust |
| `X4` interpretation | current `X4` read remains: bounded-worker capable, but not admitted as a broad toolchain-owner or long autonomous messy-worker default |

