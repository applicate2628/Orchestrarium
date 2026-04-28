# Task - Staged UX Runtime Review And Reentry Gate

You are reviewing a publish-console runtime under `candidate/review-target/`.
Do not patch that package. Produce staged UX review artifacts only.

Current source IDs:

- `S1`: stale remote source must block publish and prioritize refresh before publish.
- `S2`: missing, pending, or failed regression proof must block publish.
- `S3`: owner-missing and source-stale combined state must prioritize source refresh before owner assignment.
- `S4`: mobile action order must place blocking remediation before the publish command.
- `S5`: auditor export must not expose owner-only notes or internal resolution notes.
- `S6`: follow-up diff after publish must preserve the published receipt and block reentry until evidence is reviewed.
- `S7`: focus after owner/source remediation must return to the changed evidence row, not the publish command.
- `S8`: `candidate/review-target/docs/stale-ux-notes.md` is stale and must be rejected.
- `S9`: disabled button opacity is not by itself a finding when a visible disabled reason is still rendered.
- `S10`: `rel="noopener"` on the docs link is intentional link hardening, not a UX blocker.
- `S11`: an empty draft label is a neutral zero-state cue, not a publish failure.
- `S12`: final closeout must list exact changed review artifact paths, validation cues, and residual risk.

Required final artifacts:

- `candidate/ux-review-state.json`
- `candidate/decision-adr.md`
- `candidate/findings.json`
- `candidate/response-gate.json`
- `candidate/closure.json`

The final answer should be concise. The verifier reads files, not prose.
