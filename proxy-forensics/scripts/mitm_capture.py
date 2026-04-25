#!/usr/bin/env python3
"""One-shot HTTPS capture script. Starts mitmproxy in background, runs
a claude-aw.cmd call through it, captures flows, parses the /v1/messages
request to reveal gateway-side behavior.

Usage (run from `proxy-forensics/` root):
  python scripts/mitm_capture.py --cmd "claude-aw.cmd --model opus" --shell --prompt "Reply with '1'."

Output:
  - mitm_flows/<timestamp>.flow  — raw mitmproxy flow dump
  - mitm_capture_<timestamp>.txt — human-readable summary
"""

import argparse
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def _kill_tree(pid):
    """Kill a process and its descendants on Windows / POSIX.

    POSIX safety: only sends SIGKILL to the process group IF `pid` is known to
    be its own group leader. The subprocess MUST have been started with
    `start_new_session=True` / `preexec_fn=os.setsid` for this to be safe;
    otherwise `os.getpgid(pid)` returns the CALLER's group and killing it
    would terminate the caller. This function refuses to send signals if the
    discovered pgid equals the current process's pgid (safety guard).
    """
    try:
        if os.name == "nt":
            # Use taskkill with /T (tree) /F (force) for reliable child cleanup
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True, timeout=10,
            )
        else:
            import signal as _sig
            try:
                child_pgid = os.getpgid(pid)
                self_pgid = os.getpgid(os.getpid())
                if child_pgid == self_pgid:
                    # Safety: child is in caller's group (started without
                    # start_new_session=True). Kill only the child PID, not
                    # the whole group — otherwise we'd kill ourselves.
                    os.kill(pid, _sig.SIGKILL)
                    return
                os.killpg(child_pgid, _sig.SIGKILL)
            except ProcessLookupError:
                # Process already exited
                pass
    except Exception as e:
        print(f"[warn] _kill_tree({pid}) failed: {e}")


def ensure_cert(timeout=30):
    """Start mitmdump briefly to generate CA cert if needed."""
    cert_path = Path.home() / ".mitmproxy" / "mitmproxy-ca-cert.pem"
    if cert_path.exists():
        return cert_path
    print("[setup] Generating mitmproxy CA cert via short mitmdump run...", flush=True)
    p = subprocess.Popen(
        ["mitmdump", "--listen-port", "8080", "--quiet"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    # Wait for cert file to appear
    for _ in range(timeout * 2):
        if cert_path.exists():
            break
        time.sleep(0.5)
    p.terminate()
    try:
        p.wait(timeout=5)
    except subprocess.TimeoutExpired:
        p.kill()
    if not cert_path.exists():
        raise RuntimeError(f"mitmproxy CA cert not created at {cert_path}")
    return cert_path


def main():
    ap = argparse.ArgumentParser(description="One-shot HTTPS capture of a Claude CLI call")
    ap.add_argument("--cmd", required=True, help="Claude CLI wrapper command (e.g. 'claude-aw.cmd --model opus')")
    ap.add_argument("--shell", action="store_true")
    ap.add_argument("--prompt", default="Reply with '1'.")
    ap.add_argument("--listen-port", type=int, default=8080)
    ap.add_argument("--output-dir", default="mitm_flows",
                    help="Directory for captured flow files (default: mitm_flows/ relative to cwd; "
                         "use proxy-forensics root as cwd to keep them inside the toolkit tree)")
    ap.add_argument("--subprocess-timeout", type=int, default=60,
                    help="Seconds to wait for Claude CLI subprocess before killing (default 60)")
    args = ap.parse_args()

    outdir = Path(args.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    flow_file = outdir / f"{ts}.flow"
    summary_file = outdir / f"{ts}_summary.txt"

    # Ensure CA cert exists
    cert_path = ensure_cert()
    print(f"[setup] CA cert: {cert_path}")

    # Start mitmdump writing flows
    print(f"[mitm] Starting mitmdump on port {args.listen_port}, writing to {flow_file}", flush=True)
    mitm_proc = subprocess.Popen(
        ["mitmdump", "--listen-port", str(args.listen_port),
         "--save-stream-file", str(flow_file), "--set", "console_eventlog_verbosity=warn"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace",
    )
    time.sleep(3)  # let mitmdump start

    # Verify it's running
    if mitm_proc.poll() is not None:
        out, err = mitm_proc.communicate()
        print(f"[ERROR] mitmdump exited early:\nstdout: {out}\nstderr: {err}")
        return 1

    try:
        # Prepare env for Claude CLI
        env = os.environ.copy()
        env["HTTPS_PROXY"] = f"http://127.0.0.1:{args.listen_port}"
        env["HTTP_PROXY"] = f"http://127.0.0.1:{args.listen_port}"
        env["NODE_EXTRA_CA_CERTS"] = str(cert_path)

        # Build command
        cmd_tokens = args.cmd.split()
        full_cmd = cmd_tokens + ["-p", args.prompt, "--effort", "low",
                                  "--tools", "", "--output-format", "json"]
        print(f"[capture] Running: {' '.join(full_cmd)} (via proxy)", flush=True)
        print(f"[capture] env HTTPS_PROXY={env['HTTPS_PROXY']}")
        print(f"[capture] env NODE_EXTRA_CA_CERTS={env['NODE_EXTRA_CA_CERTS']}")

        # v0.6: subprocess.run(shell=True, timeout=...) hangs on Windows when
        # the child process (or its descendants) doesn't exit cleanly. Replace
        # with Popen + poll loop + forced kill to guarantee return within
        # timeout budget.
        # v0.6 follow-up (codex round 7 blocker): on POSIX, start child in its
        # own session so we can safely kill its process group without killing
        # the parent. `start_new_session=True` is a cross-Python-version
        # shorthand that sets preexec_fn=os.setsid on POSIX and is a no-op
        # on Windows.
        t0 = time.monotonic()
        print(f"[capture] starting subprocess (timeout={args.subprocess_timeout}s)...", flush=True)
        popen_kwargs = dict(
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
            shell=args.shell, env=env,
        )
        if os.name != "nt":
            popen_kwargs["start_new_session"] = True
        p = subprocess.Popen(full_cmd, **popen_kwargs)
        deadline = t0 + args.subprocess_timeout
        killed_reason = None
        while True:
            if p.poll() is not None:
                break
            if time.monotonic() > deadline:
                killed_reason = "timeout"
                print(f"[capture] subprocess timeout {args.subprocess_timeout}s — killing tree", flush=True)
                _kill_tree(p.pid)
                break
            time.sleep(0.5)
        try:
            stdout, stderr = p.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            _kill_tree(p.pid)
            stdout, stderr = p.communicate(timeout=5)
        elapsed = time.monotonic() - t0
        rc = p.returncode

        print(f"[capture] exit={rc}  elapsed={elapsed:.1f}s  killed={killed_reason}")
        print(f"[capture] stdout head: {stdout[:200]!r}")
        print(f"[capture] stderr head: {stderr[:400]!r}")
        r = type("R", (), {"returncode": rc, "stdout": stdout, "stderr": stderr})()  # stub for compat

        # Give mitmdump a moment to flush
        time.sleep(2)

    finally:
        # Stop mitmdump
        print(f"[mitm] Stopping mitmdump...", flush=True)
        mitm_proc.terminate()
        try:
            mitm_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            mitm_proc.kill()

    # Summarize
    print(f"\n[done] Flow file: {flow_file} (size={flow_file.stat().st_size if flow_file.exists() else 'missing'} bytes)")

    # Parse flows with mitmproxy.io.FlowReader
    if flow_file.exists() and flow_file.stat().st_size > 0:
        from mitmproxy import io as mio
        from mitmproxy.http import HTTPFlow
        summary_lines = [f"MITM Capture Summary {ts}", "=" * 60]
        with flow_file.open("rb") as f:
            reader = mio.FlowReader(f)
            flow_count = 0
            for flow in reader.stream():
                if not isinstance(flow, HTTPFlow):
                    continue
                flow_count += 1
                req = flow.request
                resp = flow.response
                summary_lines.append(f"\n--- Flow {flow_count} ---")
                summary_lines.append(f"Request:  {req.method} {req.pretty_url}")
                summary_lines.append(f"  host: {req.host}")
                summary_lines.append(f"  headers:")
                for k, v in req.headers.items():
                    # Redact auth tokens
                    if k.lower() in ("authorization", "x-api-key", "anthropic-api-key"):
                        v = "<REDACTED>"
                    summary_lines.append(f"    {k}: {v}")
                if req.content:
                    body_preview = req.get_text()[:3000] if req.get_text() else f"<{len(req.content)} bytes binary>"
                    summary_lines.append(f"  body ({len(req.content)} bytes):")
                    summary_lines.append(f"    {body_preview}")
                if resp:
                    summary_lines.append(f"Response: {resp.status_code}")
                    summary_lines.append(f"  headers:")
                    for k, v in resp.headers.items():
                        summary_lines.append(f"    {k}: {v[:120]}")
                    if resp.content:
                        body_preview = resp.get_text()[:2000] if resp.get_text() else f"<{len(resp.content)} bytes binary>"
                        summary_lines.append(f"  body ({len(resp.content)} bytes):")
                        summary_lines.append(f"    {body_preview}")
                else:
                    summary_lines.append(f"Response: <none / aborted>")
        summary_file.write_text("\n".join(summary_lines), encoding="utf-8")
        print(f"[summary] {flow_count} HTTP flows captured → {summary_file}")
        print("\n" + "=" * 60)
        print("\n".join(summary_lines[-60:]))  # tail
    else:
        print("[summary] No flows captured (file empty/missing).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
