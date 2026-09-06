"""Apply the reviewed exact-source patch and run bounded, recorded verification."""
from __future__ import annotations

import base64
import gzip
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

SOURCE = "d63884623f73b748618f47cba142faea537338be"
TREE = "65e505d0866ba615b1911d9688cae5ebfdfb3507"
PATCH = "525be6b891a74baedc95e36e0da1280367ca3eb4cc5b0397155d48a03d726fa7"
PACKED = "da1ffdd2e12f3b180fc63a8ccd71ed2760f98d89d29f017b1fe85a58d3131db7"
CONTROL = Path(__file__).resolve().parent


def output(root, *args):
    return subprocess.check_output(args, cwd=root, text=True).strip()


def main():
    root = Path(sys.argv[1]).resolve()
    evidence = Path(sys.argv[2]).resolve()
    mode = sys.argv[3]
    evidence.mkdir(parents=True, exist_ok=True)
    if output(root, "git", "rev-parse", "HEAD") != SOURCE:
        raise SystemExit("source head moved")
    if output(root, "git", "status", "--porcelain"):
        raise SystemExit("source checkout is not clean")
    packed = base64.b64decode(b"".join((CONTROL / f"patch.part{i}").read_bytes()
                                     for i in range(7)), validate=True)
    if hashlib.sha256(packed).hexdigest() != PACKED:
        raise SystemExit("transport digest mismatch")
    patch = gzip.decompress(packed)
    if hashlib.sha256(patch).hexdigest() != PATCH:
        raise SystemExit("patch digest mismatch")
    path = evidence / "candidate.patch"
    path.write_bytes(patch)
    subprocess.run(["git", "apply", "--check", str(path)], cwd=root, check=True)
    subprocess.run(["git", "apply", "--index", str(path)], cwd=root, check=True)
    if output(root, "git", "write-tree") != TREE:
        raise SystemExit("candidate tree mismatch")
    subprocess.run(["git", "diff", "--cached", "--check"], cwd=root, check=True)
    (evidence / "identity.json").write_text(json.dumps(
        {"source": SOURCE, "tree": TREE, "patch_sha256": PATCH,
         "python": sys.version, "platform": sys.platform}, indent=2), encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(CONTROL) + os.pathsep + env.get("PYTHONPATH", "")
    codes = {}

    def run(name, args):
        with (evidence / f"{name}.log").open("w", encoding="utf-8") as stream:
            try:
                result = subprocess.run(args, cwd=root, env=env, stdout=stream,
                                        stderr=subprocess.STDOUT, timeout=2700)
                code = result.returncode
            except subprocess.TimeoutExpired:
                stream.write("\nAUDIT TIMEOUT: verification incomplete\n")
                code = 124
        codes[name] = code
        print(f"{name}: exit={code}", flush=True)
        (evidence / "steps.json").write_text(json.dumps(codes, indent=2), encoding="utf-8")

    run("publication", [sys.executable, "scripts/check-publication-gate.py"])
    if codes["publication"] != 0:
        raise SystemExit("publication preflight failed")
    commit_env = env | {"GIT_AUTHOR_NAME": "github-actions[bot]",
                        "GIT_AUTHOR_EMAIL": "41898282+github-actions[bot]@users.noreply.github.com",
                        "GIT_COMMITTER_NAME": "github-actions[bot]",
                        "GIT_COMMITTER_EMAIL": "41898282+github-actions[bot]@users.noreply.github.com",
                        "GIT_AUTHOR_DATE": "2026-09-06T13:40:00Z",
                        "GIT_COMMITTER_DATE": "2026-09-06T13:40:00Z"}
    subprocess.run(["git", "commit", "-m",
                    "fix: close PR 4 installer and publication audit regressions"],
                   cwd=root, env=commit_env, check=True)
    commit = output(root, "git", "rev-parse", "HEAD")
    (evidence / "candidate-head.txt").write_text(commit + "\n", encoding="utf-8")
    if mode == "prepare":
        return 0
    if mode == "tests":
        capture = evidence / "pytest-capture.json"
        env["ORCH_CAPTURE"] = str(capture)
        run("pytest", [sys.executable, "-m", "pytest", "-q", "-p", "pr4_capture",
                       f"--junitxml={evidence / 'junit.xml'}"])
        if not capture.is_file():
            raise SystemExit("no pytest terminal evidence")
        state = json.loads(capture.read_text(encoding="utf-8"))
        selected = state["selected_nodeids"]
        complete = state["completed"]
        if (not state["finished"] or not selected or
                len(selected) != len(set(selected)) or
                sorted(selected) != sorted(complete)):
            raise SystemExit("collected/completed test coverage mismatch")
    elif mode == "contracts":
        tracked = output(root, "git", "ls-files", "*.py").splitlines()
        for relative in tracked:
            compile((root / relative).read_bytes(), relative, "exec")
        run("ruff", [sys.executable, "-m", "ruff", "check", "--select", "E9,F63,F7,F82",
                     "scripts", "src.codex", "src.claude", "tests", "install.py"])
        run("codex", [sys.executable, "src.codex/skills/lead/scripts/validate-skill-pack.py"])
        run("claude", [sys.executable, "src.claude/agents/scripts/validate-skill-pack.py"])
        run("mirrors", [sys.executable, "scripts/sync-universal-hooks.py", "--check"])
    else:
        raise SystemExit("unknown verification mode")
    subprocess.run(["git", "diff", "--exit-code"], cwd=root, check=True)
    if output(root, "git", "write-tree") != TREE:
        raise SystemExit("tests changed the staged source")
    return 0 if codes and all(code == 0 for code in codes.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
