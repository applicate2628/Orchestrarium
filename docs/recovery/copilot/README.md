# Historical recovery candidate

Recovery only: not integrated, not release-ready, not native-qualified.

Source: unpublished changes on sdk-copilot-integration at commit
`5f0515accd608fd451ce0840dafe6f266715cfcb`. The original dirty files were
left untouched. sources.json records source-relative locations and hashes of
byte-identical new candidate files, stored with a .candidate suffix.

The patch isolates selected historical changes relative to that source commit.
Do not apply it blindly to current SDK or main: shared installer and SDK code
have evolved. This is a preservation artifact, not an executable delivery.
No model, provider runtime, external review or GitHub Actions run was started.
Reconstructed Python syntax and candidate test syntax were checked; no test
suite or native acceptance was run for this recovery artifact.

Scope: offline instruction producer, default-home namespace and ledger binding,
installer/uninstaller receipt handling, and six source/test candidates. Existing
published transport and shared document helpers are not duplicated. The shipped
client catalog is not changed. Native discovery, instruction loading, hooks,
custom-home support and complete lifecycle integration remain unqualified.
Historical custom-home/hook refusals are retained for review, not adopted as
new project policy. Review their necessity against current requirements before
integration. Existing current installer changes must remain authoritative.

## Terms and Abbreviations

- SDK: software development kit.
- SHA-256: content hash used to identify preserved bytes, not acceptance evidence.
