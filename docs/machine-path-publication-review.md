# Exact machine-path publication review

Machine-local path findings now participate in the existing reviewed publication policy as the general `machine-path-prefix-v1` detector. There are no repository, pull-request, filename or path-value allowlists. A reviewer decision for one occurrence cannot approve another occurrence, including another path on the same line.

The canonical path owner exposes exact character spans using its existing patterns and placeholder filter. The scanner maps these to original UTF-8 byte coordinates. A record uses `nf-machine-path-match-v1`, a null assignment and one exact occurrence witness. The detector meaning binds the captured classifier source SHA-256. An unavailable classifier capability or unproved UTF-8 mapping grants no credit. Existing non-reviewed detection stays in force.

The existing trusted policy owner remains the only promotion/revocation route. A caller first receives the real specialist decision, resolves `machine-path`, analyzes and projects its exact approved region, and binds the record to the repository, raw path, complete blob identity, occurrence and context. It then uses `promote_decision` with expected preimage hashes. Reports or labels in a repository do not supply authority. `revoke_decision` withdraws credit through the same owner. No automatic approval or direct policy-file editing is added.

Native V3/V4 retain their policy snapshot, currentness and used-decision checks. The qualified receiver-scoped V5 form carries the same review evidence through pending capture and finalization before one-use consumption; a scoped receipt does not erase or replace review authorization. Scope/selection mismatch, revoked or changed policy, other paths and secret findings still refuse publication. Receiver scoping and exact reviewed classification are separate mechanisms.

Tests use isolated repositories and synthetic trusted decisions. A successful local native push proves that delivery route, not authorization to publish a consumer repository. Deployment and promotion of a real decision must follow the existing installation, trust and receiving process. Updating source alone does not update an installed hook, and old grants tied to a different classifier source must not silently gain new meaning.

## Generated candidates, not hand-written exceptions

The scanner's `build_review_occurrences(raw, path, object_format=..., git_mode=..., policy_module=...)` builds sorted candidate occurrences from the owner's captured ordinary text blob. The existing detector pipeline supplies matches; the producer calculates Git object identity, byte regions, full-blob context and stable finding IDs. No repository name, pull-request number, known path, blob ID or count is embedded in the algorithm. Supported Git modes match the existing policy owner: regular and executable files. Unrepresented or incomplete findings are not converted into exception candidates.

The existing trusted receiving owner may pass its complete unsealed record body and received reviewer rows to `publication_review_policy.prepare_candidate_review`. Each row contains exactly `id`, `verdict` (`approve` or `reject`), and a nonempty `reason`. The projection recomputes each generated ID over all occurrence fields before selecting anything. Unknown, duplicate or changed IDs fail; omitted and rejected findings receive no credit. The resulting record retains the existing owner-provided repository, modes, range scope, removal condition and provenance. Reviewer decisions must cover that scope; a matching finding ID alone does not authorize changing scope.

This helper is pure data projection. It does not authenticate a document or role, receive a decision, write policy, publish, or turn a digest into approval. There is no new command-line import route. The real receiving owner still obtains the actual reviewer decision and uses the existing separately authorized `promote_decision` operation with current preimages, serialization and independent readback. An authenticated receiving adapter remains outside this change; do not describe these helpers as an automatic end-to-end workflow.

Offline tests generate 1, 6 and 1000 distinct occurrences, use actual scanner partial-credit evaluation, reject edited occurrence fields and invalid verdicts, and verify that revocation restores findings. Synthetic test authority does not establish authority for a user's repository.

## Terms and Abbreviations

- API: application programming interface; these helpers are callable library functions, not new terminal commands.
- Git OID: Git object identifier, calculated from the captured blob's type, size and bytes.
- Finding ID: deterministic correlation identifier for an exact occurrence; not reviewer authentication or publication permission.
