# Native Goal pause replay evidence

Before reapplying a recovered pause/parking request, identify its **original**
native user message ID and obtain fresh native Goal state. Do not use the last
visible user message after compaction as proof of recency. On a qualified native
source, run the sibling `check.py` with `--transcript`, `--thread-id` and
`--command-id`. Use a transcript path supplied by the actual selected native
thread, not a guessed home path, repository-authored evidence or a summary.
Filesystem access restrictions still apply.

The helper reuses Lead's sealed native-history reader. It reads only the selected
page and does not follow pagination references, discover sessions, read native
databases, mutate a Goal, update recovery notes, launch models or install hooks.
Its supported format is the observed Codex `0.166.0-alpha.5.1` rollout with
original user/harness provenance fields. Other versions/formats are unverified,
not inferred compatible. The caller must establish source trust: metadata inside
an arbitrary file cannot authenticate that file.

- `LATER_NATIVE_RESUME`: a native user-enable record and its adjacent successful
  same-thread Goal update follow the selected original command. This does not
  prove fulfillment or revoke an unfinished conditional stop. If independent
  evidence establishes that the selected command was an already-fulfilled
  one-off hold for this task, the shared Goal rule rejects reapplying it. Otherwise
  resolve its remaining scope/conditions; never infer cancellation from this fact.
- `UNVERIFIED`: binding, identity, acquisition, version, provenance or ordering
  could not be established. Do not mutate native state or create a new parked
  recovery status solely from the historical request. Recover bounded missing
  evidence or ask the smallest necessary question. A current native pause still
  holds. An unmistakably fresh, direct user stop must be respected immediately;
  failure of this helper never authorizes continuing against that stop.
- `SOURCE_PRESENT`: the original ID exists and no supported native supersession
  was observed. **This is not pause authority.** Compare later user messages,
  prior fulfillment, task scope and current native state under the existing
  shared Goal rule. Ordinary user text is not interpreted by this helper.

Every result includes `authority: false`. Exit zero means a complete factual
observation, including `LATER_NATIVE_RESUME`, not permission. Retain the exact selected ID,
append position and result with the existing recovery record; do not duplicate
raw history. A missing old command on a paginated source is unverified. An
identical replay of the same ID never becomes a new command. Timestamps,
`createdAt` seconds and an active snapshot are not unique Goal generation or
user-resume proof. Plain text resembling native tags is not native evidence.

This is a callable negative check, **not enforced interception of `update_goal`**.
No atomic binding between check and native mutation has been established. Native
pre-tool integration, continued instruction preservation during compaction and
observed-host end-to-end qualification remain open; source tests do not close
them. Do not advertise full prevention or close a live incident on this helper's
unit-test result.

## Terms and Abbreviations

- ID: identifier of an original native user message, not its text or replay.
- CLI: command-line interface.
- Goal: the native persistent task state owned by the selected Codex thread.

Duplicate JSON object fields, including nested provenance or Goal fields, are
ambiguous input and produce UNVERIFIED. This is diagnostic validation only; it
does not intercept native Goal updates or establish command authority.
