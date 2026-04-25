# Round-8 codex review: v0.6 post-blocker fixes

Round 7 was RED with 4 exact blockers. All fixed. Requesting final GREEN/RED verdict.

## Blockers applied

### 1. POSIX `_kill_tree` safety (was: unsafe — could kill caller's group)
- Added `start_new_session=True` to Popen on POSIX so child runs in its own group
- Added safety guard in `_kill_tree`: if `os.getpgid(pid) == os.getpid()` group, kill only child PID (not pgid), otherwise safely killpg the isolated child group
- Added `ProcessLookupError` handling for already-exited children
- Tests: `posix_child_in_own_group_killpg_fires`, `posix_safety_guard_prevents_caller_kill`, `posix_dead_child_no_raise`
- Files: `mitm_capture.py:35-67, 123-134`

### 2. `tokenizer_probe.py` now accepts valid single-object CLI JSON (was: treated any non-list as intercepted)
- `run_probe_call` now checks `_looks_like_claude_single_object()` heuristic matching `fingerprint.py:312-336`
- Requires `result` string + (usage with tokens OR claude-hyphen model OR ≥8-char session_id) for valid single-object acceptance
- Non-list JSON without protocol fields remains `"intercepted"` (correct)
- File: `tokenizer_probe.py:114-150`

### 3. Docstring threshold drift fixed
- Header now matches code: `claude_bpe_weak` residual `[5, 10)`, `non_claude` residual `≥ 10` with stable repeats
- File: `tokenizer_probe.py:20-28`

### 4. Stale docs updated — all three locations cleaned
- `baselines.json:226-232` `known_gaps`: marked tokenizer + distill+middleware as IMPLEMENTED in v0.6
- `README.md:197`: "Known gaps (v0.6)" with ✅ crossed out for implemented items
- `METHODOLOGY.md:192`: "Known gaps (v0.6)" with same treatment

## Current state

| File | State |
|---|---|
| `fingerprint.py` | v0.6, 124 tests pass |
| `tokenizer_probe.py` | v0.1, 33 tests pass |
| `mitm_capture.py` | v0.6, 9 tests pass |
| `network_probe.py` | v0.1 (no new tests this round) |
| `baselines.json` | scorer_version 0.6.0, known_gaps updated |
| `README.md` | v0.6, known_gaps updated |
| `METHODOLOGY.md` | v0.6, known_gaps updated |
| **Total unit tests** | **166, 0 failures** |
| Live validation | A-clean high confidence on `claude --model claude-opus-4-7` |

## Your task

Verify the 4 blockers are actually resolved. Look for any regression introduced by the fixes.

Output:
```
### Summary (1 sentence)
### Blocker 1 status
### Blocker 2 status
### Blocker 3 status
### Blocker 4 status
### Any regression
### Verdict
GREEN (ship v0.6) / RED (list remaining blockers)
```

If GREEN, explicitly confirm v0.6 is shippable for hypothesis-generator scope. If RED, name specific blockers only.
