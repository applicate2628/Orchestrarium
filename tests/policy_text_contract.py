"""Test-only Markdown selection and bounded lexical formatting support."""

import re

_HEADING = re.compile(r"^ {0,3}(#{1,6})\s+(.+)$")
_CODE_SPAN = re.compile(r"(?P<ticks>`+)(?P<body>[^`]*)(?P=ticks)(?!`)")
_ATOM_SEPARATORS = frozenset("`*'\"=,:;()[]{}<>")
_CODE_ATOM_SEPARATORS = _ATOM_SEPARATORS - {"`", "*"}


def plain(text: str) -> str:
    text = re.sub(r"(?<!\w)[*_]{1,2}|[*_]{1,2}(?!\w)|`", "", text)
    return " ".join(text.translate(str.maketrans("‐‑‒–—−", "------")).split())


def lexical(text: str) -> str:
    return plain(text).casefold()


def identifier_present(text: str, identifier: str) -> bool:
    """Match original atom characters; never apply prose or whitespace normalization."""
    if not identifier:
        return False
    code_spans = [match.span("body") for match in _CODE_SPAN.finditer(text)]

    def boundary(offset: int, *, code: bool = False) -> bool:
        return (offset < 0 or offset >= len(text)
                or text[offset].isspace()
                or text[offset] in (_CODE_ATOM_SEPARATORS if code else _ATOM_SEPARATORS))

    for match in re.finditer(re.escape(identifier), text):
        start, end = match.span()
        code_span = next(((left, right) for left, right in code_spans
                          if left <= start and end <= right), None)
        if code_span is not None:
            left, right = code_span
            if ((start == left or boundary(start - 1, code=True))
                and (end == right or boundary(end, code=True))):
                return True
            continue
        if boundary(start - 1) and boundary(end):
            return True
        # Paired outer emphasis is formatting; underscores inside code remain literal.
        for marker in ("_", "__"):
            if (text[max(0, start - len(marker)):start] == marker
                and text[end:end + len(marker)] == marker
                and boundary(start - len(marker) - 1) and boundary(end + len(marker))):
                return True
    return False


def selected_section(text: str, title: str) -> str:
    """Select one heading; fenced content and example subsections are not policy."""
    lines = []
    fenced = False
    example_depth = None
    for line in text.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if fenced:
            continue
        heading = _HEADING.match(line)
        if heading:
            depth = len(heading[1])
            if example_depth is not None and depth <= example_depth:
                example_depth = None
            if re.match(r"examples?(?:$|[: ])", lexical(heading[2])):
                example_depth = depth
        if example_depth is None:
            lines.append(line)
    headings = [(i, len(m[1]), lexical(m[2])) for i, line in enumerate(lines)
                if (m := _HEADING.match(line))]
    matches = [(i, depth) for i, depth, name in headings if name == lexical(title)]
    if len(matches) != 1:
        raise AssertionError(f"selected policy section {title!r}: expected one, got {len(matches)}")
    start, depth = matches[0]
    end = next((i for i, level, _ in headings if i > start and level <= depth), len(lines))
    result = "\n".join(lines[start + 1:end]).strip()
    if not result:
        raise AssertionError(f"selected policy section {title!r} is empty")
    return result


def selected_unit(text: str, section: str, marker: str) -> str:
    body = selected_section(text, section)
    paragraphs = re.split(r"\n\s*\n|\n(?=\s*(?:[-*]|\d+[.)]) )", body)
    matches = [p for p in paragraphs
               if lexical(re.sub(r"^\s*(?:[-*]|\d+[.)]) ", "", p)).startswith(lexical(marker))]
    if len(matches) != 1:
        raise AssertionError(f"selected policy unit {section}/{marker}: expected one, got {len(matches)}")
    result = matches[0]
    if marker.endswith(":"):
        # Only the caller-selected leading label introduces the unit's duty scope.
        # An internal colon retains its preceding qualifier rather than resetting it.
        unlisted = re.sub(r"^\s*(?:[-*]|\d+[.)]) ", "", result)
        label, result = unlisted.split(":", 1)
        for emphasis in ("**", "__", "*", "_", "`"):
            if label.startswith(emphasis) and result.startswith(emphasis):
                result = result[len(emphasis):]
                break
        result = result.lstrip()
    return result


def relationships(unit: str, required: dict[str, str]) -> dict[str, bool]:
    """Check complete scoped relationship prefixes, never punctuation-separated suffixes."""
    normalized = lexical(re.sub(r"^\s*(?:[-*]|\d+[.)]) ", "", unit))
    starts = [0, *(match.end() for match in re.finditer(r"[.;]\s+", normalized))]
    return {name: any(normalized.startswith(lexical(phrase), start) for start in starts)
            for name, phrase in required.items()}
