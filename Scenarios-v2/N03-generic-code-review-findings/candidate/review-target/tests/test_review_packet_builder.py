from src.review_packet_builder import collect_changed_paths, stable_fingerprint


def test_collect_changed_paths_keeps_modified_entries():
    entries = [
        {"path": "src/router.py", "status": "modified"},
        {"path": "src/formatter.py", "status": "modified"},
    ]

    assert collect_changed_paths(entries) == ["src/router.py", "src/formatter.py"]


def test_stable_fingerprint_depends_on_path_line_and_title():
    finding = {
        "path": "src/router.py",
        "line": 18,
        "title": "Missing branch coverage",
    }

    assert stable_fingerprint(finding) == stable_fingerprint(finding)
