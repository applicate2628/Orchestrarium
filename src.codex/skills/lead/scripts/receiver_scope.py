"""Receiver-scope parser for the qualified target-local transport owner.

Only a controller-owned transport reader may supply bytes. Parsing trace files,
ls-remote output, environment values, or hook-provided advertisements is forbidden.
The caller must qualify that OS boundary before using any exclusion.
"""
from dataclasses import dataclass
import re

OID = re.compile(rb'(?:[0-9a-f]{40}|[0-9a-f]{64})\Z')
MAX_ROWS = 100_000
MAX_LINE_BYTES = 4096
MAX_TOTAL_BYTES = 32 * 1024 * 1024

REF = re.compile(rb'refs/(?:[^\x00-\x20\x7f~^:?*\[\\]+)\Z')

@dataclass(frozen=True)
class Invocation:
    nonce: bytes
    endpoint: str
    helper_identity: bytes
    git_process_identity: tuple[int, int]

class ReceiverScope:
    def __init__(self, invocation, *, owned_channel, qualified_route):
        self.invocation = invocation
        self._channel = owned_channel
        self._qualified = qualified_route
        self._roots = None
        self._invalid = False
        self._used = False

    def capture(self, lines, *, channel, invocation):
        # One complete list-for-push response, never an appended trace or a
        # later independent probe. A repeated/changed capture invalidates scope.
        if (channel is not self._channel or invocation != self.invocation
                or self._roots is not None or self._invalid or not self._qualified):
            self._invalid = True
            return False
        roots = set(); names = set(); width = None; complete = False; total = 0
        for index, line in enumerate(lines):
            if complete or not isinstance(line, bytes) or index >= MAX_ROWS:
                self._invalid = True; return False
            total += len(line)
            if len(line) > MAX_LINE_BYTES or total > MAX_TOTAL_BYTES:
                self._invalid = True; return False
            if line.startswith(b':object-format '):
                if index != 0 or line not in (b':object-format sha1\n', b':object-format sha256\n'):
                    self._invalid = True; return False
                width = 40 if line == b':object-format sha1\n' else 64
                continue
            if line == b'\n':
                complete = True; continue
            # Attributes/symrefs/unknown states are unsupported: conservative
            # full graph rather than guessing an object or a filtered list.
            fields = line[:-1].split(b' ')
            if (len(fields) != 2 or not line.endswith(b'\n')
                    or not OID.fullmatch(fields[0]) or not REF.fullmatch(fields[1])
                    or fields[1] in names or fields[1].endswith((b'.',b'/'))
                    or b'..' in fields[1] or b'@{' in fields[1]
                    or any(part.startswith(b'.') or part.endswith(b'.lock') or not part for part in fields[1].split(b'/'))):
                self._invalid = True; return False
            oid, name = fields
            if width is not None and len(oid) != width:
                self._invalid = True; return False
            width = len(oid); names.add(name)
            if set(oid) != {48}: roots.add(oid.decode('ascii'))
        if not complete:
            self._invalid = True; return False
        self._roots = frozenset(roots)
        return True

    def consume(self, *, invocation, channel, local_object_exists):
        if (self._invalid or self._used or self._roots is None
                or channel is not self._channel or invocation != self.invocation):
            return None  # None is full-graph fallback, never empty scan.
        self._used = True
        # An advertised object absent locally cannot justify guessed ancestry.
        return frozenset(oid for oid in self._roots if local_object_exists(oid))
