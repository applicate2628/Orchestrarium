#!/usr/bin/env python3
"""Verifier for V3L01A - analyst harder cross-file mis-citation sample.

Fact-table oracle (S06 family), hardened for mis-citation: each confirmed fact must be cited to the
AUTHORITATIVE source (config/effective.py, the runtime override) with the effective VALUE. A plausible
surface citation (config/defaults.py declared value, or the stale legacy doc) fails the File and value
binding. The mis-cited sources must be explicitly rejected in a dedicated table. Read-only; executes
no candidate code.

Near-peer separation: the wrong citation is PLAUSIBLE (the value literally appears in defaults.py and
the legacy doc), so a near-peer analyst that cites the surface definition mis-cites; a top analyst
traces the override to effective.py and rejects the surface sources.
"""

import argparse
import json
import re
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Check the V3L01A analyst bundle shape or a completed citation memo.")
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument("--bundle-root", type=Path, default=default_root)
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--changed-path", dest="changed_paths", action="append", default=[])
    return parser.parse_args()


def load_contract(bundle_root: Path):
    return json.loads((bundle_root / "oracle" / "citation-contract.json").read_text(encoding="utf-8"))


def strip_quotes(value: str):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_simple_yaml(path: Path):
    data = {}
    current_key = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - "):
            if current_key is not None:
                data.setdefault(current_key, []).append(strip_quotes(line[4:].strip()))
            continue
        if line.startswith(" "):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "[]":
            data[key] = []
            current_key = None
        elif value:
            data[key] = strip_quotes(value)
            current_key = None
        else:
            data[key] = []
            current_key = key
    return data


def top_level_yaml_keys(path: Path):
    keys = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.startswith(" ") or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        keys.append(line.split(":", 1)[0].strip())
    return keys


def require(condition, message, errors):
    if not condition:
        errors.append(message)


def extract_section_bodies(markdown_text: str):
    sections = {}
    current_section = None
    current_lines = []
    for line in markdown_text.splitlines():
        if line.startswith("## "):
            if current_section is not None:
                sections[current_section] = "\n".join(current_lines).strip()
            current_section = line.strip()
            current_lines = []
            continue
        if current_section is not None:
            current_lines.append(line)
    if current_section is not None:
        sections[current_section] = "\n".join(current_lines).strip()
    return sections


def parse_markdown_table(body: str):
    rows = []
    header = None
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line.startswith("|") or not line.endswith("|"):
            continue
        escaped = line.replace("\\|", "\x00")
        cells = [cell.strip().replace("\x00", "|") for cell in escaped.strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        if header is None:
            header = cells
            continue
        rows.append(cells)
    return header, rows


def row_to_dict(header, row):
    n = len(header)
    if len(row) > n:
        merged_last = " | ".join(row[n - 1:])
        row = row[: n - 1] + [merged_last]
    elif len(row) < n:
        row = row + [""] * (n - len(row))
    return {header[i]: row[i] for i in range(n)}


def parse_int_cell(value: str):
    match = re.match(r"\s*`?(\d+)`?\s*$", value)
    return int(match.group(1)) if match else None


def any_keyword_in(text_lower, keywords):
    return any(keyword.lower() in text_lower for keyword in keywords)


def all_terms_in(text_lower, terms):
    return all(term.lower() in text_lower for term in terms)


def check_changed_paths(changed_paths, allowed_paths, errors):
    allowed = set(allowed_paths)
    unexpected = sorted({path for path in changed_paths if path not in allowed})
    if unexpected:
        errors.append("Changed path outside the allowed change surface: " + ", ".join(unexpected))


def check_bundle_shape(bundle_root: Path, contract, errors):
    for entry in contract["required_top_level_entries"]:
        require((bundle_root / entry).exists(), f"Missing top-level entry: {entry}", errors)
    for relative_path in contract["required_bundle_paths"]:
        require((bundle_root / relative_path).exists(), f"Missing required bundle path: {relative_path}", errors)
    scenario_path = bundle_root / "scenario.yaml"
    require(scenario_path.exists(), "Missing scenario.yaml", errors)
    if scenario_path.exists():
        require(
            top_level_yaml_keys(scenario_path) == contract["scenario_yaml_fields"],
            "scenario.yaml fields do not match the required contract order exactly",
            errors,
        )
        require(
            parse_simple_yaml(scenario_path) == contract["required_metadata"],
            "scenario.yaml metadata does not match V3L01A",
            errors,
        )


def fact_row_matches(candidate, oracle, allowed_questions_lower):
    question_cell = candidate.get("Question", "").strip().strip("`").lower()
    if question_cell not in [q.lower() for q in oracle["question_values"]]:
        return False
    if question_cell not in allowed_questions_lower:
        return False
    file_cell = candidate.get("File", "").strip().strip("`")
    if file_cell != oracle["file"]:
        return False
    line_value = parse_int_cell(candidate.get("Line", ""))
    if line_value is None or line_value not in oracle["acceptable_lines"]:
        return False
    symbol_cell = candidate.get("Symbol", "").strip().lower()
    if not any_keyword_in(symbol_cell, oracle["symbol_keywords"]):
        return False
    fact_cell = candidate.get("Fact", "").strip().lower()
    if not all_terms_in(fact_cell, oracle["fact_terms"]):
        return False
    return True


def rejected_row_matches(candidate, oracle):
    theme_cell = candidate.get("Mis-Cited Source", "").strip().lower()
    if not any_keyword_in(theme_cell, oracle["theme_keywords"]):
        return False
    file_cell = candidate.get("File", "").strip().strip("`")
    if file_cell != oracle["file"]:
        return False
    why_cell = candidate.get("Why Wrong", "").strip().lower()
    if not all_terms_in(why_cell, oracle["rejection_terms"]):
        return False
    return True


def unknown_row_matches(candidate, oracle):
    unknown_cell = candidate.get("Unknown", "").strip().lower()
    if not any_keyword_in(unknown_cell, oracle["term_keywords"]):
        return False
    why_cell = candidate.get("Why", "").strip().lower()
    if not any_keyword_in(why_cell, oracle["why_terms"]):
        return False
    return True


def assign_rows(candidates, oracles, matcher_fn):
    matched_pairs = []
    used = set()
    for oracle in oracles:
        picks = [idx for idx, cand in enumerate(candidates) if idx not in used and matcher_fn(cand, oracle)]
        if not picks:
            matched_pairs.append((oracle, None))
        else:
            used.add(picks[0])
            matched_pairs.append((oracle, picks[0]))
    return matched_pairs


def check_table(section_bodies, section_name, header_key, count_key, oracles_key, matcher_fn, contract, errors, extra=None):
    body = section_bodies.get(section_name, "")
    header, rows = parse_markdown_table(body)
    require(header is not None, f"Missing table in {section_name}", errors)
    if header is None:
        return
    require(header == contract[header_key], f"{section_name} header mismatch: expected {contract[header_key]}, got {header}", errors)
    if header != contract[header_key]:
        return
    candidates = [row_to_dict(header, row) for row in rows]
    require(len(candidates) == contract[count_key], f"{section_name} row count mismatch: expected {contract[count_key]}, got {len(candidates)}", errors)
    if extra is not None:
        matches = assign_rows(candidates, contract[oracles_key], lambda c, o: matcher_fn(c, o, extra))
    else:
        matches = assign_rows(candidates, contract[oracles_key], matcher_fn)
    for oracle, picked in matches:
        if picked is None:
            errors.append(f"{section_name}: oracle {oracle['id']} has no matching row (file={oracle.get('file', 'n/a')})")


def check_completed_memo(bundle_root: Path, contract, errors):
    memo_path = bundle_root / contract["editable_memo"]
    require(memo_path.exists(), f"Missing candidate file: {contract['editable_memo']}", errors)
    if errors:
        return
    text = memo_path.read_text(encoding="utf-8")
    section_bodies = extract_section_bodies(text)

    for section in contract["required_memo_sections"]:
        require(section in text, f"Missing memo section: {section}", errors)
    for marker in contract["disallowed_markers"]:
        require(marker not in text, f"Disallowed marker present: {marker}", errors)

    gate_pattern = re.compile(rf"(?m)^{re.escape(contract['expected_gate_decision'])}$")
    require(gate_pattern.search(text) is not None, f"Memo does not contain gate decision {contract['expected_gate_decision']} on its own line", errors)

    allowed_questions_lower = [q.lower() for q in contract["allowed_question_values"]]
    check_table(section_bodies, "## Confirmed Facts", "confirmed_facts_table_header", "exact_confirmed_fact_count",
                "required_confirmed_facts", fact_row_matches, contract, errors, extra=allowed_questions_lower)
    check_table(section_bodies, "## Mis-Cited Sources Rejected", "rejected_table_header", "exact_rejected_count",
                "required_rejected_sources", rejected_row_matches, contract, errors)
    check_table(section_bodies, "## Explicit Unknowns", "unknowns_table_header", "exact_unknown_count",
                "required_unknowns", unknown_row_matches, contract, errors)


def main():
    args = parse_args()
    bundle_root = args.bundle_root.resolve()
    if not bundle_root.exists():
        print(f"Bundle root does not exist: {bundle_root}", file=sys.stderr)
        return 1

    errors = []
    contract = load_contract(bundle_root)
    check_bundle_shape(bundle_root, contract, errors)
    if args.changed_paths:
        check_changed_paths(args.changed_paths, contract["required_metadata"]["allowed_change_surface"], errors)
    if not args.bundle_shape_only:
        check_completed_memo(bundle_root, contract, errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    mode = "bundle shape" if args.bundle_shape_only else "completed citation memo"
    print(f"V3L01A verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
