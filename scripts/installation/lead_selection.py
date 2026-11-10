"""Pure parsing for explicit replacement of a modified receipted Lead.

The three hashes are selection data, not receipt validation, ownership proof or
permission to act. The physical installer binds them to current observations.
"""
from __future__ import annotations


_ERROR = "E_CANONICAL_LEAD_SELECTION_INVALID"


def parse_modified_lead_selection(
    values: tuple[str, ...],
) -> tuple[str, str, str] | None:
    """Accept one v1:receipt-bytes:current-tree-v2:staged-tree-v2 selection."""
    if type(values) is not tuple or len(values) > 1:
        raise ValueError(_ERROR)
    if not values:
        return None
    value = values[0]
    if type(value) is not str:
        raise ValueError(_ERROR)
    parts = value.split(":")
    if (len(parts) != 4 or parts[0] != "v1"
            or any(len(part) != 64 or any(char not in "0123456789abcdef" for char in part)
                   for part in parts[1:])):
        raise ValueError(_ERROR)
    return parts[1], parts[2], parts[3]
