from __future__ import annotations

import hashlib
import runpy
from pathlib import Path

ROOT = Path.cwd()
CONTROL = Path(__file__).resolve().parent

runpy.run_path(str(CONTROL / "pr4-r3.py"), run_name="__main__")

helper = ROOT / "scripts/check-hook-health.py"
normalized = helper.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
actual = hashlib.sha256(normalized).hexdigest()

validator = ROOT / "src.codex/skills/lead/scripts/validate-skill-pack.py"
text = validator.read_text(encoding="utf-8")
old = "1ce4ce47e923c1dc92ea6ecae3ff79872b77217eae75d4d58b0f47a53b6bf2bb"
if text.count(old) != 1:
    raise SystemExit("Codex hook-health sidecar pin anchor mismatch")
validator.write_text(text.replace(old, actual, 1), encoding="utf-8", newline="\n")
print(f"Codex hook-health normalized sidecar pin: {actual}")
