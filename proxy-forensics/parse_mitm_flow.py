#!/usr/bin/env python3
"""Parse a mitmproxy flow file and print structured summary."""
import sys
import json
from pathlib import Path
from mitmproxy import io as mio
from mitmproxy.http import HTTPFlow


def redact(headers, keys=("authorization", "x-api-key", "anthropic-api-key", "cookie", "set-cookie")):
    return {k: ("<REDACTED>" if k.lower() in keys else v) for k, v in headers.items()}


def main(flow_file):
    flow_file = Path(flow_file)
    print(f"Reading: {flow_file} ({flow_file.stat().st_size} bytes)\n")
    with flow_file.open("rb") as f:
        reader = mio.FlowReader(f)
        for i, flow in enumerate(reader.stream(), 1):
            if not isinstance(flow, HTTPFlow):
                print(f"--- Flow {i} ({type(flow).__name__}) ---")
                continue
            req = flow.request
            resp = flow.response
            print(f"=== Flow {i} ===")
            print(f"{req.method} {req.pretty_url}")
            print(f"Host: {req.host}:{req.port}")
            print(f"HTTP version: {req.http_version}")
            print(f"Request headers:")
            for k, v in redact(req.headers).items():
                print(f"  {k}: {v[:200]}")
            if req.content:
                body = req.get_text() if req.get_text() else f"<{len(req.content)} bytes binary>"
                # Try pretty-print JSON
                try:
                    parsed = json.loads(body)
                    pretty = json.dumps(parsed, indent=2, ensure_ascii=False)
                    print(f"Request body ({len(req.content)} bytes, JSON pretty):\n{pretty[:4000]}")
                except Exception:
                    print(f"Request body ({len(req.content)} bytes):\n{body[:4000]}")
            if resp:
                print(f"\nResponse: {resp.status_code} {resp.reason}")
                print(f"Response headers:")
                for k, v in redact(resp.headers).items():
                    print(f"  {k}: {v[:200]}")
                if resp.content:
                    body = resp.get_text() if resp.get_text() else f"<{len(resp.content)} bytes binary>"
                    print(f"Response body ({len(resp.content)} bytes):\n{body[:3000]}")
            else:
                print(f"Response: <none / aborted>")
            print()


if __name__ == "__main__":
    main(sys.argv[1])
