"""Validate lexical matcher output before the Python policy consumes it."""

import json


PROTOCOL_HEADER = b"orche-match-spans-v1\n"


def decode_batch(frame, rows, rules):
    """Return ordered rule/match pairs, or reject the entire frame."""
    try:
        if not frame.endswith(b"\n") or b"\n" in frame[:-1]:
            raise ValueError
        result = json.loads(frame)
        if not isinstance(result, list) or len(result) != len(rows):
            raise ValueError

        return tuple(_decode_row(row, text, binary, rules)
                     for row, (text, binary) in zip(result, rows, strict=True))
    except (IndexError, RecursionError, TypeError, ValueError):
        # Neither content nor individual captures belong in diagnostics.
        raise ValueError("invalid matcher frame") from None


def _decode_row(row, text, binary, rules):
    if not isinstance(row, list):
        raise ValueError
    if not row:
        return ()

    data = text.encode("utf-8")
    offsets = {0}
    for entry in row:
        if not isinstance(entry, list) or len(entry) != 2:
            raise ValueError
        rule_id, spans = entry
        if type(rule_id) is not int or not 0 <= rule_id < len(rules):
            raise ValueError
        binary_rule, rule = rules[rule_id]
        if binary and not binary_rule:
            raise ValueError
        if not isinstance(spans, list) or len(spans) != 1 + rule.groups or spans[0] is None:
            raise ValueError
        for span in spans:
            if span is None:
                continue
            if not isinstance(span, list) or len(span) != 2:
                raise ValueError
            start, end = span
            if type(start) is not int or type(end) is not int or not 0 <= start <= end <= len(data):
                raise ValueError
            offsets.update(span)

    positions = {0: 0}
    previous = position = 0
    for offset in sorted(offsets):
        position += len(data[previous:offset].decode("utf-8"))
        positions[offset] = position
        previous = offset

    observations = []
    previous_key = (-1, -1)
    for rule_id, spans in row:
        coordinates = tuple((-1, -1) if span is None
                            else (positions[span[0]], positions[span[1]]) for span in spans)
        start, end = coordinates[0]
        key = (rule_id, start)
        if start == end or key <= previous_key:
            raise ValueError
        match = rules[rule_id][1].match(text, start)
        if match is None or match.regs != coordinates:
            raise ValueError
        previous_key = key
        observations.append((rule_id, match))
    return tuple(observations)
