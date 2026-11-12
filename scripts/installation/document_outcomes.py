"""Pure byte-to-renderer adapter; no reads, writes, receipt or storage authority.

The renderer is the existing producer supplied by its caller, never a second
merge implementation. Codex and Claude preparation use this adapter; receipt
ownership remains a separate lifecycle decision.
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


def _document_map(provider: str, scope: str) -> dict[str, str]:
    client = get_client(provider)
    if scope not in {"global", "project"}:
        raise ValueError("E_DOCUMENT_OUTCOMES_SCOPE")
    return client["documents"][scope]


def _decode_preimage(provider: str, raw: bytes | None) -> tuple[str | None, str]:
    if raw is not None and type(raw) is not bytes:
        raise ValueError("E_DOCUMENT_OUTCOMES_BYTES")
    text = None if raw is None else raw.decode("utf-8")
    return text, "exact-newlines"


def _render_prepared(
    path: str,
    kind: str,
    raw: bytes | None,
    text: str | None,
    mode: str,
    renderer: Callable[[str, str | None], str],
) -> DocumentResult:
    rendered = renderer(kind, text)
    if type(rendered) is not str:
        raise ValueError("E_DOCUMENT_OUTCOMES_RENDERED_TEXT")
    return DocumentResult(path, kind, raw, text, rendered.encode("utf-8"), mode)


def render_document(
    provider: str,
    scope: str,
    path: str,
    before: bytes | None,
    renderer: Callable[[str, str | None], str],
) -> DocumentResult:
    """Render one validated logical document from already acquired bytes.

    The provider/scope map owns the kind. This single-document operation permits
    sequential preparation without requiring other document preimages.
    renderer(kind, existing) must be a pure existing producer with its source
    payload bound by the caller; purity is not a sandbox guarantee.
    """
    documents = _document_map(provider, scope)
    if type(path) is not str or path not in documents:
        raise ValueError("E_DOCUMENT_OUTCOMES_PATH")
    if not callable(renderer):
        raise ValueError("E_DOCUMENT_OUTCOMES_RENDERER")
    text, mode = _decode_preimage(provider, before)
    return _render_prepared(path, documents[path], before, text, mode, renderer)


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
    documents = _document_map(provider, scope)
    if type(preimages) is not dict or set(preimages) != set(documents):
        raise ValueError("E_DOCUMENT_OUTCOMES_INPUT_SET")
    if not callable(renderer):
        raise ValueError("E_DOCUMENT_OUTCOMES_RENDERER")
    # Snapshot the map before callbacks. Bytes are immutable and are retained
    # separately from the text view supplied to the existing producer.
    prepared = []
    for path, kind in documents.items():
        raw = preimages[path]
        text, mode = _decode_preimage(provider, raw)
        prepared.append((path, kind, raw, text, mode))
    return tuple(_render_prepared(*item, renderer) for item in prepared)
