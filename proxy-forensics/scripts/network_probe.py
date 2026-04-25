#!/usr/bin/env python3
"""
Network-level fingerprinting for Claude-compatible proxy endpoints.

Complements fingerprint.py (model-behavior probes) with orthogonal evidence:
  - TLS certificate chain (issuer, SAN, expiry)
  - Response headers (proxy-software fingerprints: LiteLLM, Portkey,
    OpenRouter, Cloudflare, AWS, Vercel, etc.)
  - Timing / latency distribution
  - Known-proxy-software signature matching

Does NOT cost LLM tokens — only TLS handshakes + HTTP requests.

Usage (run from `proxy-forensics/` root):
  python scripts/network_probe.py --url https://api.claudecodeapi.cloud
  python scripts/network_probe.py --url https://api.anthropic.com --label "direct"

Output: structured evidence dict (JSON) — useful alongside fingerprint.py
output for cross-evidence analysis.
"""

import argparse
import json
import socket
import ssl
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

NETWORK_PROBE_VERSION = "0.1.0"

# Known proxy-software header fingerprints.
# Each entry: substring → (software, confidence 0-1, notes).
PROXY_SIGNATURES = {
    # Middleware / aggregators
    "x-litellm-": ("LiteLLM", 0.9, "Header prefix is LiteLLM-specific"),
    "x-portkey-": ("Portkey", 0.9, "Portkey proxy middleware"),
    "openrouter": ("OpenRouter", 0.7, "OpenRouter route marker"),
    "helicone": ("Helicone", 0.9, "Helicone observability proxy"),
    # Hosting / CDN
    "cf-ray": ("Cloudflare", 0.95, "CF-Ray ID header"),
    "cf-cache-status": ("Cloudflare", 0.95, "CF cache header"),
    "x-amz-cf-id": ("CloudFront", 0.95, "AWS CloudFront distribution"),
    "x-vercel-": ("Vercel", 0.9, "Vercel edge/serverless"),
    "fly-request-id": ("Fly.io", 0.9, "Fly.io platform"),
    "x-render-": ("Render", 0.9, "Render.com hosting"),
    "x-railway-": ("Railway", 0.85, "Railway.app hosting"),
    # Real Anthropic
    "anthropic-ratelimit-": ("Anthropic-direct", 0.95, "Anthropic-specific ratelimit header"),
    "anthropic-organization-id": ("Anthropic-direct", 0.95, "Anthropic org header"),
    # Generic server identifiers
    "server: nginx": ("nginx", 0.3, "Generic nginx — doesn't identify proxy software"),
    "server: envoy": ("envoy", 0.6, "Envoy proxy — common in service-mesh setups"),
    "server: caddy": ("Caddy", 0.6, "Caddy server"),
}


def inspect_tls(hostname, port=443, timeout=10):
    """Connect via TLS, extract cert details without verifying chain."""
    try:
        ctx = ssl.create_default_context()
        # We want to see cert even if it's untrusted — disable verification
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection((hostname, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert(binary_form=False)  # parsed form needs verification
                # Fall back to binary form + openssl parsing via cryptography if unavailable
                der = ssock.getpeercert(binary_form=True)
                cipher = ssock.cipher()  # (name, version, bits)
                proto = ssock.version()
                # Parsed cert only works if check_hostname/verify were on. Extract manually.
                return {
                    "hostname": hostname,
                    "port": port,
                    "tls_version": proto,
                    "cipher_suite": cipher[0] if cipher else None,
                    "cipher_bits": cipher[2] if cipher else None,
                    "cert_der_size_bytes": len(der) if der else None,
                    "cert_parsed": cert or None,
                    "handshake_success": True,
                }
    except (socket.timeout, ConnectionError, ssl.SSLError, OSError) as e:
        return {"hostname": hostname, "port": port, "handshake_success": False, "error": str(e)}


def fetch_headers(url, method="GET", timeout=15, body=None, extra_headers=None):
    """Issue a request (with no auth — expect 401/405/400) and capture response headers.

    Purposely unauth'd so we don't burn tokens / trip rate limits. A good
    proxy should still return CDN/middleware headers in the error response.
    """
    if body is not None and isinstance(body, str):
        body = body.encode("utf-8")
    req = Request(url, method=method, data=body)
    req.add_header("User-Agent", "proxy-forensics-network-probe/0.1")
    for k, v in (extra_headers or {}).items():
        req.add_header(k, v)
    t0 = time.monotonic()
    try:
        resp = urlopen(req, timeout=timeout)
        elapsed = time.monotonic() - t0
        return {
            "status_code": resp.status,
            "headers": {k.lower(): v for k, v in resp.headers.items()},
            "elapsed_ms": round(elapsed * 1000, 1),
            "url_final": resp.url,
            "method": method,
        }
    except HTTPError as e:
        elapsed = time.monotonic() - t0
        return {
            "status_code": e.code,
            "headers": {k.lower(): v for k, v in (e.headers.items() if e.headers else [])},
            "elapsed_ms": round(elapsed * 1000, 1),
            "url_final": getattr(e, "url", url),
            "method": method,
        }
    except (URLError, socket.timeout, OSError) as e:
        return {"status_code": None, "error": str(e), "headers": {}, "elapsed_ms": None, "method": method}


def probe_with_fallback(base_url, hostname, port, scheme):
    """Try multiple request shapes to get headers. Aggressive gateways
    may drop GET / immediately but respond to POST /v1/messages with body.
    """
    attempts = []
    # 1. GET /v1/messages (Anthropic API convention)
    url = f"{scheme}://{hostname}:{port}/v1/messages"
    r = fetch_headers(url, method="GET")
    attempts.append(("GET /v1/messages", r))
    if r.get("status_code"):
        return r, attempts
    # 2. POST /v1/messages with minimal body (what real Claude CLI does)
    r = fetch_headers(url, method="POST",
                      body='{"model":"claude-opus-4-7","messages":[{"role":"user","content":"x"}],"max_tokens":1}',
                      extra_headers={"Content-Type": "application/json"})
    attempts.append(("POST /v1/messages", r))
    if r.get("status_code"):
        return r, attempts
    # 3. GET / (bare root)
    url = f"{scheme}://{hostname}:{port}/"
    r = fetch_headers(url, method="GET")
    attempts.append(("GET /", r))
    return r, attempts


def timing_profile(url, n=5, timeout=10):
    """Measure RTT distribution across N unauth'd requests."""
    samples = []
    for _ in range(n):
        try:
            req = Request(url, method="GET")
            req.add_header("User-Agent", "proxy-forensics-network-probe/0.1")
            t0 = time.monotonic()
            try:
                urlopen(req, timeout=timeout)
            except HTTPError:
                pass  # expected — unauth'd
            samples.append((time.monotonic() - t0) * 1000)
        except (URLError, socket.timeout, OSError) as e:
            samples.append(None)
    valid = [s for s in samples if s is not None]
    if not valid:
        return {"samples_ms": samples, "median_ms": None, "min_ms": None, "max_ms": None}
    valid_sorted = sorted(valid)
    median = valid_sorted[len(valid_sorted) // 2]
    return {
        "samples_ms": [round(s, 1) if s is not None else None for s in samples],
        "valid_count": len(valid),
        "median_ms": round(median, 1),
        "min_ms": round(min(valid), 1),
        "max_ms": round(max(valid), 1),
        "jitter_ms": round(max(valid) - min(valid), 1),
    }


def detect_proxy_software(headers_dict):
    """Match response headers against known proxy-software fingerprints.

    Returns list of (software, confidence, reason) tuples, ordered by confidence.
    """
    findings = []
    # Normalize headers for matching: "key: value" lowercased lines
    lines = []
    for k, v in headers_dict.items():
        lines.append(f"{k.lower()}: {v.lower() if isinstance(v, str) else v}")
    combined = "\n".join(lines)

    for signature, (software, confidence, notes) in PROXY_SIGNATURES.items():
        if signature.lower() in combined:
            findings.append({
                "software": software,
                "confidence": confidence,
                "matched_signature": signature,
                "notes": notes,
            })

    findings.sort(key=lambda x: -x["confidence"])
    return findings


def classify_network_evidence(tls_info, headers_info, timing_info, proxy_matches):
    """Roll up network evidence into a summary verdict."""
    all_fetches_failed = headers_info.get("status_code") is None
    tls_err_text = str(tls_info.get("error", "")).lower()
    # Aggressive defense pattern: server accepts TCP connection but then
    # either drops during TLS handshake or refuses to send HTTP response.
    # Distinguish from "DNS failure / offline" (network problem, not defense).
    # Indicators of server-side drop (as opposed to network unreachable):
    tls_dropped_indicators = [
        "unexpected_eof", "forcibly closed", "connection reset", "sslerror",
        "handshake operation timed out", "handshake timed out",
        "tlsv1_alert", "sslv3_alert",
    ]
    tls_dropped = any(ind in tls_err_text for ind in tls_dropped_indicators)
    aggressive_defense = (
        (tls_info.get("handshake_success") and all_fetches_failed)
        or (not tls_info.get("handshake_success") and tls_dropped)
    )
    summary = {
        "tls_ok": tls_info.get("handshake_success", False),
        "reached_endpoint": headers_info.get("status_code") is not None,
        "http_status": headers_info.get("status_code"),
        "aggressive_defense": aggressive_defense,
        "latency_median_ms": timing_info.get("median_ms") if timing_info else None,
        "proxy_software_detected": [m["software"] for m in proxy_matches],
        "high_confidence_proxy": [m["software"] for m in proxy_matches if m["confidence"] >= 0.85],
        "anthropic_direct_headers": any(
            m["software"] == "Anthropic-direct" for m in proxy_matches
        ),
        "cdn_detected": any(
            m["software"] in ("Cloudflare", "CloudFront") for m in proxy_matches
        ),
        "middleware_detected": any(
            m["software"] in ("LiteLLM", "Portkey", "OpenRouter", "Helicone") for m in proxy_matches
        ),
    }

    notes = []
    if summary["aggressive_defense"]:
        notes.append(
            "Aggressive defense detected: server accepts TCP connection then drops during "
            "TLS handshake or refuses HTTP without valid auth. This is itself middleware-like "
            "behavior — legitimate origins typically return proper HTTP errors with headers."
        )
    if not summary["reached_endpoint"]:
        notes.append("Endpoint did not return parseable HTTP response — no header evidence available")
    elif not summary["proxy_software_detected"]:
        notes.append("No known proxy-software signatures detected — either direct origin, custom middleware, or signatures stripped")
    if summary["anthropic_direct_headers"]:
        notes.append("Anthropic-specific headers present — strong signal for Anthropic-direct (can still be forged)")
    if summary["middleware_detected"]:
        notes.append(f"Middleware proxy-software detected: {[m['software'] for m in proxy_matches if m['software'] in ('LiteLLM', 'Portkey', 'OpenRouter', 'Helicone')]}")
    if timing_info and timing_info.get("jitter_ms", 0) > 500:
        notes.append(f"High jitter ({timing_info['jitter_ms']} ms) — suggests variable upstream routing")

    summary["notes"] = notes
    return summary


def main():
    ap = argparse.ArgumentParser(description=f"Claude proxy network-fingerprinting probe v{NETWORK_PROBE_VERSION}")
    ap.add_argument("--url", required=True, help="Gateway base URL (e.g. https://api.claudecodeapi.cloud)")
    ap.add_argument("--label", default="target", help="Display label")
    ap.add_argument("--timing-runs", type=int, default=5, help="Number of timing probes (default 5)")
    ap.add_argument("--save-raw", help="Path to save full JSON output")
    args = ap.parse_args()

    parsed = urlparse(args.url)
    hostname = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    print(f"=== Network fingerprinting: {args.label} ===")
    print(f"    url: {args.url}")
    print(f"    host: {hostname}:{port}\n")

    print("[1/3] TLS inspection...", flush=True)
    tls_info = inspect_tls(hostname, port)
    if tls_info.get("handshake_success"):
        print(f"      tls_version: {tls_info.get('tls_version')}")
        print(f"      cipher:      {tls_info.get('cipher_suite')} ({tls_info.get('cipher_bits')} bits)")
        print(f"      cert_size:   {tls_info.get('cert_der_size_bytes')} bytes")
    else:
        print(f"      TLS FAILED: {tls_info.get('error')}")

    print("\n[2/3] Header fingerprinting (unauth'd, multiple shapes)...", flush=True)
    headers_info, attempts = probe_with_fallback(args.url, hostname, port, parsed.scheme)
    for name, r in attempts:
        if r.get("status_code"):
            print(f"      {name}: status={r['status_code']}  elapsed={r['elapsed_ms']} ms")
        else:
            print(f"      {name}: FAILED ({r.get('error', 'unknown')[:100]})")
    if headers_info.get("status_code"):
        print(f"      headers (from successful attempt, method={headers_info.get('method')}):")
        for k, v in sorted(headers_info.get("headers", {}).items()):
            print(f"        {k}: {v[:80]}")
    else:
        print(f"      All fetch attempts failed — endpoint actively refuses unauth'd requests")

    print("\n[3/3] Timing profile...", flush=True)
    timing_info = timing_profile(args.url, n=args.timing_runs)
    if timing_info.get("median_ms") is not None:
        print(f"      median: {timing_info['median_ms']} ms   min: {timing_info['min_ms']}   max: {timing_info['max_ms']}   jitter: {timing_info['jitter_ms']}")
        print(f"      samples ({args.timing_runs}): {timing_info['samples_ms']}")
    else:
        print(f"      TIMING FAILED")

    print("\n[*] Proxy-software signature matching...", flush=True)
    proxy_matches = detect_proxy_software(headers_info.get("headers", {}))
    if proxy_matches:
        for m in proxy_matches:
            print(f"      [{m['confidence']:.2f}] {m['software']}: {m['matched_signature']}  — {m['notes']}")
    else:
        print(f"      No signatures matched.")

    print("\n=== Network evidence summary ===")
    summary = classify_network_evidence(tls_info, headers_info, timing_info, proxy_matches)
    for k, v in summary.items():
        if k == "notes":
            continue
        print(f"  {k}: {v}")
    if summary["notes"]:
        print(f"\n  Notes:")
        for n in summary["notes"]:
            print(f"    - {n}")

    if args.save_raw:
        full = {
            "target": args.label,
            "url": args.url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "probe_version": NETWORK_PROBE_VERSION,
            "tls": tls_info,
            "headers": headers_info,
            "timing": timing_info,
            "proxy_matches": proxy_matches,
            "summary": summary,
        }
        with open(args.save_raw, "w", encoding="utf-8") as f:
            json.dump(full, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n  raw saved to {args.save_raw}")


if __name__ == "__main__":
    sys.exit(main())
