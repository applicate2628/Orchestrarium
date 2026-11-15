"""Pure exact-current Claude instruction selection parsing.

This module only validates caller-supplied names and digest strings. It does not
read files, validate current bytes, acquire ownership, or create receipt history.
The physical installer remains responsible for those separate boundaries.
"""
from __future__ import annotations


_ERROR = "E_CLAUDE_INSTRUCTION_SELECTION_INVALID"


def _validate_name(name: str) -> None:
    if (type(name) is not str or not name
            or any(not char.isprintable() or char.isspace() for char in name)
            or any(char in name for char in '\\:="<>|?*')):
        raise ValueError(_ERROR)
    parts = name.split("/")
    if (len(parts) < 2 or parts[0] not in {"agents", "commands"}
            or parts[0] == "agents" and len(parts) != 2
            or any(not part or part in {".", ".."} or part.endswith(".")
                   or part.casefold() in {"__pycache__", "receipts"}
                   for part in parts)
            or not parts[-1].casefold().endswith(".md")
            or len(parts[-1]) <= 3):
        raise ValueError(_ERROR)


def parse_claude_instruction_grants(
    values: tuple[str, ...], source_names: frozenset[str]
) -> dict[str, str]:
    """Parse PATH=SHA256 selections in input order, without mutating inputs.

    Every name in the source catalog must be valid and casefold-unambiguous.
    A grant must use that catalog's exact spelling; no normalization, alias
    resolution, source-derived grants, or truthy force switch is supported.
    Empty selections return an empty mapping, not adoption or history.
    All invalid inputs raise ValueError with the same stable error code.
    """
    if type(values) is not tuple or type(source_names) is not frozenset:
        raise ValueError(_ERROR)
    catalog_keys = set()
    for name in source_names:
        _validate_name(name)
        key = name.casefold()
        if key in catalog_keys:
            raise ValueError(_ERROR)
        catalog_keys.add(key)

    result = {}
    selected_keys = set()
    for value in values:
        if type(value) is not str or value.count("=") != 1:
            raise ValueError(_ERROR)
        name, digest = value.split("=", 1)
        _validate_name(name)
        key = name.casefold()
        if (name not in source_names or key in selected_keys
                or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest)):
            raise ValueError(_ERROR)
        selected_keys.add(key)
        result[name] = digest
    return result



_CODEX_DOCUMENT_ERROR = "E_CODEX_DOCUMENT_SELECTION_INVALID"


def parse_codex_document_grant(
    values: tuple[str, ...]
) -> tuple[str, tuple[int, int]] | None:
    """Parse one exact SHA256:START:END selection without acquiring authority.

    Offsets are canonical nonnegative ASCII character indices with END > START.
    Current-document length and digest validation belong to the common validator.
    Empty selections return None; all invalid inputs share one stable error code.
    """
    if type(values) is not tuple or len(values) > 1:
        raise ValueError(_CODEX_DOCUMENT_ERROR)
    if not values:
        return None
    value = values[0]
    if type(value) is not str or value.count(":") != 2:
        raise ValueError(_CODEX_DOCUMENT_ERROR)
    digest, start_text, end_text = value.split(":")
    if (len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)):
        raise ValueError(_CODEX_DOCUMENT_ERROR)
    for offset in (start_text, end_text):
        if (not offset
                or any(char not in "0123456789" for char in offset)
                or len(offset) > 1 and offset[0] == "0"):
            raise ValueError(_CODEX_DOCUMENT_ERROR)
    try:
        start, end = int(start_text), int(end_text)
    except ValueError as exc:
        raise ValueError(_CODEX_DOCUMENT_ERROR) from exc
    if end <= start:
        raise ValueError(_CODEX_DOCUMENT_ERROR)
    return digest, (start, end)


_CLAUDE_RECEIPT_ERROR = "E_CLAUDE_RECEIPT_SELECTION_INVALID"


def parse_claude_receipt_grant(values: tuple[str, ...]) -> str | None:
    """Parse an explicit raw-receipt SHA256 pin, never inferred permission."""
    if type(values) is not tuple or len(values) > 1:
        raise ValueError(_CLAUDE_RECEIPT_ERROR)
    if not values:
        return None
    digest = values[0]
    if (type(digest) is not str or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)):
        raise ValueError(_CLAUDE_RECEIPT_ERROR)
    return digest


def claude_instruction_grants_from_receipt(
    receipt: bytes, digest: str, scope: str, source_names: frozenset[str]
) -> dict[str, str]:
    """Expand a pinned receipt into exact source-listed instruction preconditions.

    Only files entries participate, with their recorded (not source) digests.
    This pure projection proves neither current file state nor historical
    authority. The installer must independently bind and check every selected
    current file before writing any selected content.
    """
    import hashlib

    try:
        from installation.ownership import decode_record
    except ModuleNotFoundError as error:
        if error.name not in {"installation", "installation.ownership"}:
            raise
        from scripts.installation.ownership import decode_record

    try:
        if (type(receipt) is not bytes or type(scope) is not str
                or scope not in {"global", "project"}):
            raise ValueError(_CLAUDE_RECEIPT_ERROR)
        parse_claude_receipt_grant((digest,))
        parse_claude_instruction_grants((), source_names)
        if hashlib.sha256(receipt).hexdigest() != digest:
            raise ValueError(_CLAUDE_RECEIPT_ERROR)
        record = decode_record(receipt, "claude", scope)
        catalog = {(".claude/" + name).casefold(): ".claude/" + name
                   for name in source_names}
        selected = []
        for path, recorded_digest in sorted(record["files"].items()):
            exact = catalog.get(path.casefold())
            if exact is None:
                continue
            if path != exact:
                raise ValueError(_CLAUDE_RECEIPT_ERROR)
            selected.append(path[len(".claude/"):] + "=" + recorded_digest)
        if not selected:
            raise ValueError(_CLAUDE_RECEIPT_ERROR)
        return parse_claude_instruction_grants(tuple(selected), source_names)
    except (ValueError, TypeError, UnicodeError, RecursionError) as error:
        raise ValueError(_CLAUDE_RECEIPT_ERROR) from error
