from __future__ import annotations

import runpy
import subprocess
from pathlib import Path

ROOT = Path.cwd()
CONTROL = Path(__file__).resolve().parent

runpy.run_path(str(CONTROL / "pr4-r4.py"), run_name="__main__")

# The broad suffix-wide eol=lf experiment changed historical CRLF payloads and
# unrelated tracked files. Restore the exact source policy and remove its test.
attributes = subprocess.run(
    ["git", "show", "HEAD:.gitattributes"],
    cwd=ROOT,
    check=True,
    capture_output=True,
).stdout
(ROOT / ".gitattributes").write_bytes(attributes)
(ROOT / "tests/test_text_eol_contract.py").unlink()

release_path = ROOT / "RELEASE_NOTES.md"
release = release_path.read_text(encoding="utf-8")
eol_bullet = (
    "- **Byte-pinned source, test, manifest, and human-contract files now checkout "
    "with Line Feed (LF) endings on every host.** Python, JavaScript Object Notation "
    "(JSON), JSON Lines, Markdown, Tom's Obvious Minimal Language (TOML), YAML Ain't "
    "Markup Language (YAML), shell, and PowerShell families are explicitly `eol=lf`, "
    "while accepted-prior fixture payloads retain their historical bytes through the "
    "later `-text` exception. **Why it matters:** Windows checkout conversion can no "
    "longer invalidate Secure Hash Algorithm 256-bit (SHA-256) pins or make an "
    "unchanged installer or projection appear corrupt.\n"
)
if release.count(eol_bullet) != 1:
    raise SystemExit("RELEASE_NOTES.md: broad EOL bullet anchor mismatch")
release = release.replace(eol_bullet, "", 1)

old_deep_audit = (
    "- **Deep-audit test and mirror contracts now match shipped runtime behavior.** "
    "Hook-health resolves the Codex executable only inside the real host probe, the "
    "SessionStart oracle reflects generic runtime discovery, the Russian Claude "
    "reference documents structured stdout advisory delivery with exit zero, and "
    "cross-host installer tests no longer pass a Portable Operating System Interface "
    "(POSIX) shim as a Windows executable. **Why it matters:** injected inventory "
    "tests, translated operator guidance, and Linux/Windows verification no longer "
    "fail or mislead for reasons unrelated to production behavior.\n"
)
new_deep_audit = (
    "- **Deep-audit test and mirror contracts now match shipped runtime behavior.** "
    "For hook-health, an injected inventory is route-authoritative evidence for that "
    "call, so only the real host-probe path resolves the Codex executable. The "
    "SessionStart oracle reflects generic runtime discovery, the Russian Claude "
    "reference documents structured stdout advisory delivery with exit zero, and "
    "cross-host installer tests no longer pass a Portable Operating System Interface "
    "(POSIX) shim as a Windows executable. **Why it matters:** injected inventory "
    "tests, translated operator guidance, and Linux/Windows verification no longer "
    "fail or mislead for reasons unrelated to production behavior.\n"
)
if release.count(old_deep_audit) != 1:
    raise SystemExit("RELEASE_NOTES.md: deep-audit bullet anchor mismatch")
release = release.replace(old_deep_audit, new_deep_audit, 1)
release_path.write_text(release, encoding="utf-8", newline="\n")

print("Removed broad EOL experiment and retained the narrow audited fixes.")
