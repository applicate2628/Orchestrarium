"""Keep the SDK delivery's native role features aligned with the main pack."""
from pathlib import Path
import hashlib
import json
import tomllib

import pytest
from tests.fixtures.runtime_capabilities import NATIVE_ROLE_DISABLED_FEATURES


ROOT = Path(__file__).resolve().parents[1]
ROLES = (
    "algorithm-scientist", "analyst", "architect", "architecture-reviewer",
    "backend-engineer", "computational-scientist", "default", "explorer",
    "knowledge-archivist", "mechanical-scout", "mechanical-worker", "planner",
    "platform-engineer", "qa-engineer", "scientific-software-engineer",
    "security-engineer", "security-reviewer", "worker",
)


@pytest.mark.parametrize("role", ROLES)
def test_native_role_disables_unused_interactive_features(role: str) -> None:
    source = ROOT / "src.codex" / "agents"
    payload = (source / f"{role}.toml").read_bytes()
    config = tomllib.loads(payload.decode("utf-8"))
    manifest = json.loads((source / "orchestrarium-role-manifest.json").read_text())
    assert manifest["roles"][role]["sha256"] == hashlib.sha256(payload).hexdigest()
    assert config["features"] == NATIVE_ROLE_DISABLED_FEATURES, role
