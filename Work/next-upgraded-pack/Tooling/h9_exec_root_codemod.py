#!/usr/bin/env python3
"""H9 codemod: route candidate-CODE execution in the 28 subprocess/import verifiers to
BENCH_EXEC_ROOT (the oracle-free exec-fixed/ root) instead of the bundle root (which under the v2.1
topology = score/, containing oracle/). Closes Terra H1 audit CRITICAL-1 (score-time candidate code
reaching the answer key).

Targeted + backward-compatible: only the candidate-code base derivations (workspace / solver_path /
module_path / renderer_path = <root> / "candidate" / ...) are retargeted; oracle/verifier reads keep
`root`. When BENCH_EXEC_ROOT is unset, `exec_root` falls back to the original base -> byte-identical
behavior, so every existing reference/test still passes.

Binary-mode read/write (Windows LF-preservation). Idempotent (skips already-migrated sites).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parents[3] / "Scenarios-v2"
CODE_VARS = ("workspace", "solver_path", "module_path", "renderer_path")
MARK = "os.environ.get(\"BENCH_EXEC_ROOT\")"

# a candidate-code base derivation line: `<indent><var> = <base> / "candidate" / ...`
SITE = re.compile(
    r'^(?P<i>[ \t]*)(?P<var>' + "|".join(CODE_VARS) + r')\s*=\s*(?P<base>root|bundle_root)\s*/\s*"candidate"',
    re.M,
)


def migrate(path: Path) -> str:
    raw = path.read_bytes()
    if MARK.encode() in raw:
        return "skip-already-migrated"
    text = raw.decode("utf-8")
    if not SITE.search(text):
        return "skip-no-site"

    # ensure `import os`
    if not re.search(r'^import os\b', text, re.M):
        m = re.search(r'^import [^\n]+$', text, re.M)
        if not m:
            return "FAIL-no-import-anchor"
        text = text[: m.start()] + "import os\n" + text[m.start():]

    def repl(mo: re.Match) -> str:
        i, var, base = mo.group("i"), mo.group("var"), mo.group("base")
        inject = (
            f'{i}exec_root = Path(os.environ["BENCH_EXEC_ROOT"]).resolve() '
            f'if os.environ.get("BENCH_EXEC_ROOT") else {base}\n'
        )
        line = mo.group(0).replace(f"= {base} /", "= exec_root /", 1)
        return inject + line

    new = SITE.sub(repl, text)
    path.write_bytes(new.encode("utf-8"))
    return "migrated"


def main() -> int:
    targets = sorted(
        p for p in BENCH.glob("*/verifiers/*.py")
        if b"subprocess" in p.read_bytes() or b"spec_from_file_location" in p.read_bytes()
    )
    counts: dict[str, int] = {}
    for p in targets:
        r = migrate(p)
        counts[r] = counts.get(r, 0) + 1
        if r.startswith("FAIL"):
            print(f"  {r}: {p}", file=sys.stderr)
    print(f"H9 codemod over {len(targets)} verifier files: {counts}")
    return 1 if any(k.startswith("FAIL") for k in counts) else 0


if __name__ == "__main__":
    raise SystemExit(main())
