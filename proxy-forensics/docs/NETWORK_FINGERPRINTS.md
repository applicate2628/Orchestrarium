# Network-Level Fingerprint Comparison

Baseline network fingerprints for known Claude endpoints, collected via `scripts/network_probe.py`. Use as reference for comparing new suspect endpoints. Sample raw outputs in `examples/network_anthropic.json` and `examples/network_aw.json`.

**Collection date**: 2026-04-24. Re-collect quarterly.

## api.anthropic.com (Anthropic direct)

```
TLS:         TLSv1.3, TLS_AES_256_GCM_SHA384 (256 bits), cert 931 bytes
HTTP status: 405 on unauth'd GET /v1/messages (expected — method not allowed)
Server:      cloudflare
CDN:         Cloudflare (cf-ray header)
Headers:
  - cache-control: private, max-age=0, no-store, no-cache, ...
  - cf-ray: <unique-per-request>
  - connection: close
  - content-security-policy: default-src 'none'; frame-ancestors 'none'
  - referrer-policy: same-origin
  - server: cloudflare
  - x-frame-options: SAMEORIGIN
  - x-robots-tag: none
Timing:      ~380 ms median, ~60 ms jitter
Anthropic-specific headers on auth'd requests: anthropic-ratelimit-*, anthropic-organization-id
```

**Fingerprint signature**: Cloudflare-fronted, strict security headers, tight timing variance, proper 405 on method mismatch.

## api.claudecodeapi.cloud (AW gateway — suspect from original investigation)

```
TLS:         INCONSISTENT — handshake often times out or drops with UNEXPECTED_EOF.
             Occasionally succeeds with TLSv1.3.
HTTP status: INCONSISTENT — most unauth'd requests are dropped at TLS/TCP layer.
             When responses make it through: 405 on GET /v1/messages
Server:      nginx (when reachable)
CDN:         None detected
Headers:     Sparse, no identifiable proxy-software signatures, no Anthropic headers
Timing:      >3000 ms median when successful, >5000 ms jitter (most requests fail)
aggressive_defense: TRUE
```

**Fingerprint signature**: aggressive drop-on-unauth defense, no CDN, bare nginx, extreme timing variance. Behavior is inconsistent with a legitimate API origin — legitimate APIs return proper HTTP errors with headers. Dropping connections during TLS is characteristic of DDoS-mitigation or custom middleware designed to resist probing.

## How to compare a new suspect

1. Run `python scripts/network_probe.py --url <suspect-url>` and save output.
2. Compare:
   - **TLS success rate**: consistent vs drops? Drops = middleware/defense.
   - **Server / CDN signatures**: Cloudflare suggests legit reseller. Bare nginx / unknown = custom infrastructure.
   - **Anthropic-specific headers**: Present = likely real Anthropic relay; absent = gateway strips or isn't actually routing through Anthropic.
   - **Latency profile**: <500ms median with <100ms jitter suggests origin/CDN. >1000ms median or >500ms jitter suggests upstream proxying.
   - **aggressive_defense flag**: True means the suspect actively refuses unauth'd probing, which is itself evidence of active middleware.

## Interpretation caveats

- A legitimate proxy can forge any header, including `server:` and Anthropic-specific ones. Don't treat headers alone as proof.
- `aggressive_defense: True` is a strong positive signal for "active middleware" but could also indicate aggressive DDoS protection by a legitimate reseller who doesn't want public probing.
- Absence of evidence (no CDN headers, no `aggressive_defense`) tells you the origin is bare-origin or has scrubbed headers — both are suspicious absent other evidence.
- Latency includes geographic distance. Compare to baselines from the same geographic region when possible.
- CDN mismatch between endpoints (Cloudflare vs nothing vs Fly.io vs …) tells you they are NOT the same infrastructure, which is useful when correlating proxy operators.

## When to extend this doc

Add a new endpoint fingerprint here whenever:
- A new suspect proxy is investigated.
- A known endpoint's fingerprint changes materially (CDN migration, server change).
- A new proxy-software signature is added to `scripts/network_probe.py`'s `PROXY_SIGNATURES` table.
