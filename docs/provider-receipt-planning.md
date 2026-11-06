# Provider receipt planning contract

This is the source contract for `scripts/installation/receipt_plan.py`, the first pure part of the existing document/managed-instruction ownership work. It reuses the SDK `ownership.py` and `configuration.py` contracts and the same provider receipt identity. It is not a second installer, a durable binding protocol, or a live migration command. The installer imports the shared pure contracts for Codex and Claude preparation, but does not call receipt planning or persist provider receipts; legacy updates are unchanged.

## Inputs and results

`plan_changes(receipt, provider, scope, outcomes, document_context)` accepts exact prior receipt bytes or explicit absence, artifact byte preimages, proposed rendered outcomes, and the existing bundled Markdown context function. File payloads and document blocks share one plan. Each immutable artifact result contains its route, exact before/after SHA-256 fingerprints and outstanding acquisition requirements. Changes contain only validated file/config entry deltas, not a serialized receipt.

- An unrecorded ordinary update stays on the legacy route and acquires nothing, even if its resulting content contains familiar markers.
- A claimed artifact must match its recorded semantic digest. Missing, changed or ambiguous content is preserved without changing its entry or falling back to legacy overwrite.
- A positive creation outcome may propose ownership only for a new file or a newly inserted block that leaves all original text intact.
- Adoption must select the exact current artifact bytes. Marked blocks retain exact outside slices; unmarked Codex adoption additionally selects a reviewed, line-bounded span under the existing SDK boundary contract. The digest and span are not user consent.
- Update and removal of a claimed document preserve exact outside text. File payload digests remain byte-exact. Other legacy artifacts are not blocked merely because a receipt exists or a different artifact is preserved.

`apply_delta(receipt, plan)` produces only an in-memory validated record projection. It rechecks the exact input receipt fingerprint, including JSON whitespace, and preserves unrelated files, directories, configuration entries and the presence/value of `layout`. A previously absent record has no layout injected. The function performs no filesystem write, serialization or publication and grants no authority to perform them. Public dataclasses are constructible: this projection validates schema/currentness, not provenance that `plan_changes` produced the supplied plan. Future integration must retain the original `Outcome`, exact adoption boundaries and separate approval evidence, rather than authorize using plan fingerprints or requirement strings alone.

`serialize_delta(receipt, plan)` validates the projection and returns candidate bytes using the common codec's `serialize_record`, which preserves layout presence/value and enforces the existing 4 MiB encoded limit. A no-op retains the exact original bytes or absence. The original `encode_record` still constructs its existing copy-layout record; both entry points share one serializer. Candidate bytes are neither persisted ownership nor permission to write.

## Compatibility and integration boundaries

The common SDK encoder currently asserts `provider-owned-copies-v1`. This hotfix has not established that layout, so the planner deliberately does not call it. No v1 field extension, new receipt schema, installation UUID or claimed persistent identity is invented here. The reused client metadata differs only in the pre-SDK Claude source/reference paths; it does not activate another host or provider.

A matching v1 digest proves only a semantic match at its logical name. It does not prove historical physical-root continuity. Every recorded proposal retains that outstanding requirement. Fresh/adoption proposals retain acquisition and exact user-approval requirements. All changes still need current artifact and receipt inputs and one atomic commit/rollback through the existing transaction owner. The plan is not a capability, and callers must not clear those requirements by trusting flags, labels or the plan itself.

Before any live integration, one owner must bind receipt and target inputs, receive actual production outcomes, preserve currentness through content-plus-receipt commit, and share the resulting record with repeat install, update and uninstall. Serialization and truthful layout are covered only as pure byte operations here. The existing transaction's commit flag and exception recovery do not establish crash-atomic multi-file publication. Link retargeting, identity reuse and filesystem-chain safety remain separate unresolved gates. Pure tests do not qualify those operations or waive their restrictions.

Receipt decisions are intentionally not enabled in default installation yet. It is the reusable semantic core for the coupled integration, not a fix claimed complete or a reason to archive the existing ownership tickets.

## Exact document outcomes and provider preparation

The pure document_outcomes.render_documents adapter accepts the complete provider document preimage set and the existing producer as a caller-supplied pure callback. It retains original UTF-8 bytes separately from renderer input, returns immutable proposed outputs, and never reads or writes a target. Codex receives exact text; Claude receives its current universal-newline view. That normalization is disclosed, not misrepresented as preservation of the raw preimage.

All document inputs are validated and decoded before rendering. Both Claude documents must render successfully before a result tuple is returned. This is an all-or-error in-memory result, not atomic storage publication; callback purity remains a caller obligation. The callbacks must use the existing producer owners, not a competing renderer.

Conversion to the existing planner always uses update intent. Neither an absent preimage, familiar markers, nor successful rendering is a positively received creation or adoption event. The adapter does not select adoption spans or grant permission. Exact bytes remain available for the planner to reject an outside-text change, including current Claude newline normalization. Public result dataclasses are not trusted capabilities.

Codex preparation now uses the common adapter. The read-only _prepare_codex_agents function retains the previous source-read and exact-newline target-read order, and returns a DocumentResult before any write. Its project_scope argument selects logical metadata: project AGENTS.md or global .codex/AGENTS.md; it does not infer authority from the physical path. The existing _merge_codex_agents wrapper calls preparation once and retains its warning, dry-run, writer and None-return contract. The writer still receives the same rendered text through the existing owner. Preparation results are proposals, not observed writes or capabilities.

Claude preparation now uses the single-document render_document adapter. It validates the logical path against the provider/scope map and shares decoding/rendering helpers with the batch API. The batch API still validates and decodes its complete input set before any callback; the single-document API lets _prepare_claude_docs retain the existing sequence: read and validate sources, read/render CLAUDE.md, then read/render AGENTS.md. Both immutable proposals are returned before the wrapper can write either. The wrapper retains its None return, dry-run output and Claude-first writer order. Exact input bytes are retained while the existing universal-newline renderer view remains unchanged. project_scope selects logical scope explicitly; neither an absent input nor a successful render acquires ownership. Receipt planning/persistence, historical storage authority, physical creation receiving, coupled writes and repeat lifecycle acceptance remain future work under the existing restrictions. Tests use AST-isolated source functions and memory-only input transport with the real pure adapter/parser, never a full installer import or physical-chain execution.

## Existing transaction-derived receipt outcome

The canonical Lead receipt finalizer now reads included payload bytes through the enabled transaction's admitted/composed image, using the existing _image_file_bytes reader. It retains the existing no-follow manifest traversal and runtime-cache exclusions. It compares that manifest with the admitted stage minus exact proven reclamations, then hashes the same compared manifest using the existing tree-manifest codec. It no longer hashes a second independent pathname census for the receipt.

The pure _canonical_lead_expected_manifest helper preserves the prior reclamation calculation. Dry-run returns before reading. Disabled direct-operation transactions retain the existing default reader rather than gaining a new full-image census. Receipt format, no-op handling and create/replace writers are unchanged. This is a connected improvement to the existing Lead receipt producer, not provider-receipt persistence or proof of historical root identity.

Qualification of this change is limited to pure manifest semantics, static source wiring and independent source review. The finalizer, physical image reader, complete directory/chain custody, cache races, transaction settlement and rollback have not been executed or qualified by those checks. Their existing restrictions remain in force; pure tests must not be represented as live lifecycle acceptance.

## Terms and Abbreviations

- Provider receipt: the version-one Orchestrarium record of claimed artifact paths and content digests.
- SDK: Software Development Kit; here, the existing SDK integration branch supplying the shared source contracts.
- SHA-256: Secure Hash Algorithm with a 256-bit digest; a content fingerprint, not proof of consent or storage identity.
- Legacy route: the existing update path for an artifact without a claimed receipt entry.
- Projection: an in-memory record after applying validated entry changes, without filesystem mutation.
- Layout: the receipt's claim about the installation arrangement; its absence must not be converted into a claim.
- Storage authority: independently established permission and identity continuity for the actual target, beyond its logical path or matching bytes.
