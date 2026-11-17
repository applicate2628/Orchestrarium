# Historical recovery candidate

Recovery only: not integrated, not release-ready, not native-qualified.

Source: unpublished changes on sdk-copilot-integration at commit
`5f0515accd608fd451ce0840dafe6f266715cfcb`. The original dirty files were
left untouched. sources.json records source-relative locations and hashes of
new candidate files, stored with a .candidate suffix. The usage test remains
byte-identical. The model-selection test replaces five synthetic absolute
run-directory fixtures with relative `private/run` values. Its original and
transformed SHA-256 hashes are recorded separately; the original is untouched.
The transformed fixture is not claimed runnable or behaviorally equivalent
without future integration and validation.

The patch isolates selected historical changes relative to that source commit.
Do not apply it blindly to current SDK or main: shared installer and SDK code
have evolved. This is a preservation artifact, not an executable delivery.
No model, provider runtime, external review or GitHub Actions run was started.
Reconstructed Python syntax and candidate test syntax were checked; no test
suite or native acceptance was run for this recovery artifact.

Scope: explicit Kimi model selection, configuration readback/drift handling,
result and SDK provenance binding, and cumulative-usage test candidates. The
usage test has no new implementation associated with it. Already published
synchronous-callback and snapshot corrections are excluded. Provider access
terms, supported models, runtime behavior and policy compatibility require
current qualification before any implementation is admitted.

## Terms and Abbreviations

- SDK: software development kit.
- SHA-256: content hash used to identify preserved bytes, not acceptance evidence.
