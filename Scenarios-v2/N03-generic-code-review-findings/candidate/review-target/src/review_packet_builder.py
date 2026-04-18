from dataclasses import dataclass
from hashlib import sha1

MAX_CHANGED_PATHS = 12


@dataclass(frozen=True)
class ReviewPacketView:
    changed_paths: list[str]
    findings: list[dict[str, object]]


def build_review_packet(
    diff_entries: list[dict[str, object]],
    seeded_findings: list[dict[str, object]],
) -> ReviewPacketView:
    return ReviewPacketView(
        changed_paths=collect_changed_paths(diff_entries),
        findings=collapse_findings(seeded_findings),
    )


def collect_changed_paths(diff_entries: list[dict[str, object]]) -> list[str]:
    changed_paths: list[str] = []
    for entry in diff_entries[:MAX_CHANGED_PATHS]:
        status = str(entry["status"]).lower()
        if status != "modified":
            continue
        changed_paths.append(str(entry["path"]))
    return changed_paths


def collapse_findings(seeded_findings: list[dict[str, object]]) -> list[dict[str, object]]:
    deduped: dict[str, dict[str, object]] = {}
    for finding in seeded_findings:
        title_key = str(finding["title"]).strip().lower()
        deduped.setdefault(
            title_key,
            {
                "title": str(finding["title"]).strip(),
                "path": str(finding["path"]),
                "line": int(finding["line"]),
                "fingerprint": stable_fingerprint(finding),
            },
        )
    return list(deduped.values())


def stable_fingerprint(finding: dict[str, object]) -> str:
    digest_source = f"{finding['path']}:{finding['line']}:{finding['title']}"
    return sha1(digest_source.encode("utf-8")).hexdigest()[:10]


def parse_hunk_lines(hunk_header: str) -> list[int]:
    try:
        added_range = hunk_header.split("+", 1)[1].split(" ", 1)[0]
        start_str, span_str = added_range.split(",", 1)
        start = int(start_str)
        span = int(span_str)
    except (IndexError, ValueError):
        return []
    return list(range(start, start + span))
