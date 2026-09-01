from __future__ import annotations

import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Any


MISSING = object()
_WHITESPACE_RUN = re.compile(r"\s+")
_DEFAULT_IGNORABLE_RANGES = (
    (0x00AD, 0x00AD),
    (0x034F, 0x034F),
    (0x061C, 0x061C),
    (0x115F, 0x1160),
    (0x17B4, 0x17B5),
    (0x180B, 0x180F),
    (0x200B, 0x200F),
    (0x202A, 0x202E),
    (0x2060, 0x206F),
    (0x3164, 0x3164),
    (0xFE00, 0xFE0F),
    (0xFEFF, 0xFEFF),
    (0xFFA0, 0xFFA0),
    (0xFFF0, 0xFFF8),
    (0x1BCA0, 0x1BCA3),
    (0x1D173, 0x1D17A),
    (0xE0000, 0xE0FFF),
)


def _is_default_ignorable(character: str) -> bool:
    codepoint = ord(character)
    return any(start <= codepoint <= end for start, end in _DEFAULT_IGNORABLE_RANGES)


def get_path(value: Any, path: str, default: Any = MISSING) -> Any:
    current = value
    if not path:
        return current
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def normalize_text(value: Any, *, casefold: bool = False) -> Any:
    if not isinstance(value, str):
        return value
    normalized = unicodedata.normalize("NFC", value).strip()
    return normalized.casefold() if casefold else normalized


def canonical_identity(value: Any) -> str:
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    compatible = unicodedata.normalize("NFKC", value)
    normalized = "".join(character for character in compatible if not _is_default_ignorable(character)).strip()
    return _WHITESPACE_RUN.sub(" ", normalized).casefold()


def normalize_scalar(
    value: Any,
    *,
    casefold: bool = False,
    aliases: dict[str, str] | None = None,
) -> Any:
    normalized = normalize_text(value, casefold=casefold)
    if aliases and isinstance(normalized, str):
        normalized_aliases = {
            normalize_text(key, casefold=casefold): normalize_text(target, casefold=casefold)
            for key, target in aliases.items()
        }
        return normalized_aliases.get(normalized, normalized)
    return normalized


def numeric_string_equivalent(actual: Any, expected: Any) -> bool:
    if not isinstance(actual, str) or isinstance(expected, bool) or not isinstance(expected, (int, float, Decimal)):
        return False
    try:
        actual_number = Decimal(actual)
        expected_number = Decimal(str(expected))
    except (InvalidOperation, ValueError):
        return False
    return actual_number.is_finite() and expected_number.is_finite() and actual_number == expected_number


def normalize_collection(value: Any, id_field: str) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        normalized = []
        for item_id in sorted(value, key=str):
            raw = value[item_id]
            item = dict(raw) if isinstance(raw, dict) else {"value": raw}
            item.setdefault(id_field, item_id)
            normalized.append(item)
        return normalized
    return []


def canonical_item_key(item: dict[str, Any]) -> str:
    return json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
