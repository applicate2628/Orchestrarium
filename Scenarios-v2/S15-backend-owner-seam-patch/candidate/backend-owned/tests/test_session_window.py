from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend_owned import build_session_window


def test_revoked_sessions_are_removed():
    grants = [
        {"user_id": "u1", "session_id": "sess-a", "expires_at": 220, "revoked": True},
    ]
    assert build_session_window(grants, 200) == []


def test_cutoff_expiry_is_not_active():
    grants = [
        {"user_id": "u1", "session_id": "sess-a", "expires_at": 200, "revoked": False},
    ]
    assert build_session_window(grants, 200) == []


def test_newest_duplicate_wins():
    grants = [
        {"user_id": "u2", "session_id": "sess-old", "expires_at": 260, "revoked": False},
        {"user_id": "u2", "session_id": "sess-new", "expires_at": 320, "revoked": False},
    ]
    assert build_session_window(grants, 200) == [
        {"user_id": "u2", "session_id": "sess-new", "expires_at": 320},
    ]


if __name__ == "__main__":
    test_revoked_sessions_are_removed()
    test_cutoff_expiry_is_not_active()
    test_newest_duplicate_wins()
    print("S15 direct tests PASS")
