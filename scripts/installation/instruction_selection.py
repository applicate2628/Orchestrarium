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
