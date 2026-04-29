# Evidence E5 - Synthetic Dry-Run Observations

The following observations come from a synthetic dry run. Sensitive strings are redacted.

1. `run-debug.json` included `PROVIDER_TOKEN=[REDACTED_PROVIDER_TOKEN]` and
   `VAULT_TOKEN=[REDACTED_VAULT_TOKEN]` because the launcher copied selected environment variables
   without an explicit allowlist.
2. The attachment manifest contained `..\\Archive\\Quarterly\\notes.md`, and the staging prototype
   attempted to resolve it before any canonical path check rejected the path.
3. Provider stdout included a fenced shell snippet and the current export prototype copied the block
   verbatim into the analyst markdown package as "helpful reproduction context."
4. Analysts with access to the export share could also open `raw-provider-stderr.txt` because the
   raw-vault path and the export path were mounted under the same broadly readable share prefix.
5. The same service account path published the analyst export and wrote raw vault artifacts, making
   later provenance and access review ambiguous.
