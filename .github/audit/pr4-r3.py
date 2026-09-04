from __future__ import annotations

from pathlib import Path

source_path = Path(__file__).with_name("pr4-r2.py")
source = source_path.read_text(encoding="utf-8")
old = '        assert b"\\r\\n" not in (ROOT / relative).read_bytes()\n'
new = '        assert b"\\\\r\\\\n" not in (ROOT / relative).read_bytes()\n'
if source.count(old) != 1:
    raise SystemExit("pr4-r2.py: CRLF literal escape anchor mismatch")
compiled = compile(source.replace(old, new, 1), str(source_path), "exec")
namespace = {"__name__": "__main__", "__file__": str(source_path)}
exec(compiled, namespace)
