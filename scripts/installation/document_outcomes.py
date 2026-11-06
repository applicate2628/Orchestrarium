"""Pure byte-to-renderer adapter; no reads, writes, receipt or storage authority.

The renderer is the existing producer supplied by its caller, never a second
merge implementation. Codex preparation uses this adapter; receipt ownership
remains a separate lifecycle decision.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .clients import get_client
from .receipt_plan import Outcome


@dataclass(frozen=True)
class DocumentResult:
    path: str
    kind: str
    before: bytes | None
    renderer_input: str | None
    after: bytes
    read_mode: str

    @property
    def change(self) -> str:
        if self.before is None:
            return "missing-preimage"
        return "unchanged" if self.before == self.after else "existing-update"

    def as_outcome(self) -> Outcome:
        # Even an absent snapshot is not a positively received creation event.
        # Receipt planning, not this adapter, decides legacy/claimed handling.
        return Outcome(self.path, "block", self.before, self.after, intent="update")


def render_documents(
    provider: str,
    scope: str,
    preimages: dict[str, bytes | None],
    renderer: Callable[[str, str | None], str],
) -> tuple[DocumentResult, ...]:
    """Render the complete provider document set from already acquired bytes.

    renderer(kind, existing) must be a pure existing producer with its source
    payload bound by the caller. All preimages are decoded before any renderer
    is called; no partial tuple is returned when any renderer refuses.
    A callback's purity is a caller requirement, not a sandbox guarantee.
    """
    client = get_client(provider)
    if scope not in {"global", "project"}:
        raise ValueError("E_DOCUMENT_OUTCOMES_SCOPE")
    documents = client["documents"][scope]
    if type(preimages) is not dict or set(preimages) != set(documents):
        raise ValueError("E_DOCUMENT_OUTCOMES_INPUT_SET")
    if not callable(renderer):
        raise ValueError("E_DOCUMENT_OUTCOMES_RENDERER")
    # Snapshot the map before callbacks. Bytes are immutable and are retained
    # separately from the text view supplied to the existing producer.
    prepared = []
    for path, kind in documents.items():
        raw = preimages[path]
        if raw is not None and type(raw) is not bytes:
            raise ValueError("E_DOCUMENT_OUTCOMES_BYTES")
        text = None if raw is None else raw.decode("utf-8")
        mode = "exact-newlines" if provider == "codex" else "universal-newlines"
        if text is not None and mode == "universal-newlines":
            text = text.replace("\r\n", "\n").replace("\r", "\n")
        prepared.append((path, kind, raw, text, mode))
    results = []
    for path, kind, raw, text, mode in prepared:
        rendered = renderer(kind, text)
        if type(rendered) is not str:
            raise ValueError("E_DOCUMENT_OUTCOMES_RENDERED_TEXT")
        results.append(DocumentResult(path, kind, raw, text,
                                      rendered.encode("utf-8"), mode))
    return tuple(results)
