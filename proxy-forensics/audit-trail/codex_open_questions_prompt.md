# Advisory: priority of 3 deferred open questions

The v0.5 Claude proxy forensic toolkit is GREEN (you approved after 6 rounds). Three open questions were deferred from scope. I need your opinion on whether each is worth pursuing, and in what order if so.

## Context

The original investigation classified `claude-aw.cmd` (routes to api.claudecodeapi.cloud) as "most consistent with: Claude-like frontier backend on Vertex AI with aggressive middleware gateway." That classification is the toolkit's current output. The 3 open items extend the investigation beyond what the toolkit already does.

## The 3 open questions

### Q1. Vision benchmark discrepancy (39 vs 75 px on coordinate-extraction)

Initial user-provided data showed official Claude Opus 4.7 producing:
- 39.3 px mean error (790 output tokens) when invoked via `env CLAUDE_CODE_EFFORT_LEVEL=max`
- 75.0 px mean error (1832 output tokens) when invoked via `--effort max` CLI flag

Hypothesis I investigated: the pin state `unpinOpus47LaunchEffort` explains the difference (CLI flag unpins, env var doesn't).

Result: A/B test with identical prompt, forced pin vs unpin on Opus 4.7 (math task) — outputs were byte-nearly-identical (698 vs 716 out_tok, same cache behavior, same system prompt). **No detectable API-level difference between the two invocation paths on a deterministic math prompt.**

So the 39 vs 75 px difference on the original vision benchmark is unexplained. Possible causes:
- Sampling variance specific to perceptual tasks (extended thinking adds drift on pixel-precision work)
- Task-dependent confound (CoT hurts vision but not math)
- Non-reproducible artifact of the specific runs
- Something we haven't identified

This is not about the proxy classification (that's closed). It's about whether official-Claude behaves oddly on vision under different CLI paths.

### Q2. Gateway operator identity / proxy-software fingerprinting

The toolkit classifies the BACKEND model. It does not identify WHO is running the proxy or WHAT proxy-software is running. Potential directions:
- Certificate chain inspection (TLS cert issuer, CDN, ASN)
- Response header fingerprinting (Server:, X-Powered-By:, quirks)
- Known-proxy-software signatures (LiteLLM? Portkey? OpenRouter-clone? Custom?)
- Timing / latency profile

Purpose: attribution (who to contact for abuse / who might be legitimate reseller).

### Q3. mitmproxy HTTPS capture

Set up local HTTPS intercepting proxy, inject CA cert into the Node runtime the Claude CLI uses, capture the actual `/v1/messages` request body going to `api.claudecodeapi.cloud`.

What this would reveal:
- Literal content of the injected system prompt (we currently only know it exists via +7 tokenizer offset + Euler-bias override behavior)
- Exact `thinking` parameter handling by the gateway (passed through? stripped? rewritten?)
- Exact `cache_control` handling
- Any other header/param manipulation

Work involved: mitmproxy install + cert generation + Claude CLI env config (`NODE_EXTRA_CA_CERTS`) + intercept rule + 1 request capture + JSON inspection. ~30-60 min setup, ~5 min capture.

## Your call

For each question, answer:
1. **Priority**: HIGH / MEDIUM / LOW / SKIP
2. **Rationale** (one sentence)
3. **ROI** (what we'd learn vs cost to investigate)

Then rank them overall (1-2-3 or SKIP).

Constraint: the toolkit classification is DONE. These are either (a) methodology extensions for future investigations of different proxies, (b) deeper forensic analysis of this specific proxy, or (c) tangential curiosities. Distinguish which each is.

Keep response under 300 words. Commit to priorities.
