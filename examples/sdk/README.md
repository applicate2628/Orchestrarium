# Explicit Windows coordination qualification example

`coordination_live_caller.py` is the retrieved historical caller, relocated into
this checkout. Only its checkout-root locator changed. The original 34,118 bytes
were recovered and verified against SHA-256
`e1a45dd690d3a3c87a6dbb4eefadfa22fd92608b2ab40f78b6c1fa945a4255a2`.
The relocation test reverses that one line and checks the historical digest.
This preserves provenance, not a fresh live qualification of this tracked file.

This is a Windows-only qualification example, not a production entry point or
cross-platform launcher. It retains the historical Luna/high profile, arithmetic
prompt, two separate native-turn reservations and bounded resource settings.
Those values describe this scenario; they are not universal SDK defaults or a
fresh spending grant. No provider or credential is provisioned automatically.

## Inputs and execution boundary

Run from the working directory selected by the existing admitted binding. Supply:

- `--binding`: current SDK subscription binding prepared through the existing
  dispatch owner, including account, runtime and current work-item identities.
- `--work-item`: existing canonically admitted work item with its status and
  admission files. This example does not create admission or a ledger.
- `--native-exe` and `--native-sha256`: explicitly selected installed Codex binary
  and its reviewed SHA-256; no fallback to another executable.
- `--source-checkpoint` and `--checkpoint-sha256`: independently reviewed JSON
  manifest and its digest. The manifest has a `manifest` object mapping
  checkout-relative paths to objects containing `sha256`. Digests are byte
  witnesses, not approval. Do not generate approval by hashing unreviewed inputs.
- `--output`: a new, absent directory for this invocation. Keep it outside the
  source tree or under its excluded `.scratch/` directory so generated evidence
  does not mutate the pinned source set. Existing output is never overwritten.

All filesystem inputs are command-line parameters; no workstation path or
account value is shipped. The source checkout is found relative to this file.
Keep the source tree quiescent during preparation and execution; file additions
and byte changes invalidate the pinned snapshot. The caller uses existing policy,
ledger, transport and process owners rather than synthesizing their approval.

With an already provisioned compatible Python environment, `python
examples/sdk/coordination_live_caller.py --help` lists the exact arguments.
Omitting `--execute` performs local preparation and writes diagnostics, but does
not launch a native worker. Preparation may reject absent or incompatible inputs;
it is not an account, hook or runtime-readiness certificate.

Only add `--execute` after fresh explicit Host/user approval for this exact
outer/inner pair and both reservations. The program cannot manufacture that
approval. Execution requires non-administrator Windows, current account/profile/
required-hook admission, the selected official SDK and Agents dependencies.
The historical environment used openai-codex 0.163.0, openai-agents 0.24.0 and
runtime 0.164.0; this list is provenance, not a substitute for current admission.
The existing runtime still checks compatibility and identity.

The output retains prepared invocation, preflight, outcomes, process closure,
inner receipt and final status. Its contents can contain private account and
machine metadata: keep outputs local, never commit them without a separate
publication review. An uncertain or failed invocation is not permission to retry.
There is no resume mode. Do not infer zero usage or absent native capabilities
from missing observations.

## Verification limits

The repository tests cover exact source relocation, syntax, import, help and
missing-argument failure without child-process or socket creation. They do not
execute a live pair, Windows Job handling, or the original 26-test host-local
suite. That suite has not been transferred. The historical live result remains
bound to the original caller and runtime, not to this relocated file or future
changes. See [coordination architecture and evidence](../../docs/codex-coordination-model.md).

## Terms and Abbreviations

- SDK: software development kit.
- Host: invoking session that owns actual permission and current admission.
- Manifest: reviewed paths and byte hashes, not an authorization record.
- Outer/inner pair: coordinator inference followed by the admitted review call.
