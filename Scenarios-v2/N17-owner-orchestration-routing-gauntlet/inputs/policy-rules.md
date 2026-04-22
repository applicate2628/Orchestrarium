# Policy Rules

- Keep exactly one primary task unless the user explicitly reprioritizes.
- After a side request, resume the primary task and state the next concrete step.
- Do not claim completion while admitted-scope follow-up remains.
- Treat diagnostic overlays separately from routing lanes until a scoring-policy decision promotes them.
- Provider quota, route failures, and wrapper timeouts are `NOT-RUN` or runtime caveats, not model failures.
- Add `X2`, `X5`, and `X6` calibration rows when a new `X1`/`X3` result could change lane policy.
- `X5` semantic runs require a direct smoke that writes `worker-output.txt` after recent Gemini no-output timeouts.
- `$lead` owns orchestration and accepted-artifact routing; `$product-manager` owns roadmap priority changes.
- `$qa-engineer` verifies accepted artifacts after they exist.
- `$architecture-reviewer` gates semantic routing-policy changes after the proposed surface exists.
