import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from releaseflow.config import select_profile


def test_select_profile_returns_some_profile():
    name, profile = select_profile(
        {
            "activeProfile": "prod",
            "legacyProfile": "staging",
            "profiles": {
                "prod": {"parallelism": 2},
                "staging": {"parallelism": 1},
            },
        }
    )

    assert name in {"prod", "staging"}
    assert "parallelism" in profile
