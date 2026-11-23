"""Source-catalog guard only; does not execute UI fixtures or evaluate an agent."""
from pathlib import Path
import re
import shlex
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
CLAUDE = ROOT / "adapters" / "claude"
if not CLAUDE.is_dir():
    CLAUDE = ROOT / "src.claude"

CHECKS = {
    "accessibility-reviewer": ("2.4.11", "2.5.7", "2.5.8 exceptions", "actual announcement", "not visual evidence", "native capture"),
    "frontend-engineer": ("stale completion", "semantic locators"),
    "model-view-engineer": ("destructive mutation", "stable identity"),
    "qt-ui-engineer": ("native mixed-DPI transition", "after close and reopen", "native capture"),
    "ui-test-engineer": ("measured window device pixel ratio", "offscreen", "native capture"),
    "ux-designer": ("user-visible completion", "participant evidence"),
    "ux-reviewer": ("unassisted walkthrough", "participant evidence", "native capture"),
    "analyzing-video-bugs": ("fps_mode passthrough", "Equal file lengths", "source presentation timestamps", "UNVERIFIED"),
    "windows-gui-manual-testing": ("DPI-virtualized", "presentation timestamps", "UNVERIFIED"),
}


@pytest.mark.parametrize("role,markers", CHECKS.items())
def test_specialist_evidence_is_projected_to_both_client_sources(role, markers):
    codex = ROOT / "src.codex" / "skills" / role / "SKILL.md"
    # Claude consumes canonical common workflows, not historical source copies.
    clients = (codex,) if role in {"analyzing-video-bugs", "windows-gui-manual-testing"} else (
        codex, CLAUDE / "agents" / (role + ".md"),
    )
    for marker in markers:
        for client in clients:
            assert marker in client.read_text(encoding="utf-8"), (client, marker)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="optional local FFmpeg evidence fixture")
def test_native_video_inspection_recipe_preserves_decoded_sequence_and_gap(tmp_path):
    clip = tmp_path / "source.mkv"
    extract = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-filter_threads", "1",
            "-f", "lavfi", "-i", "testsrc2=size=32x32:rate=120:duration=0.05",
            "-vf", "setpts='if(lt(N,3),N,N+2)'", "-fps_mode", "passthrough",
            "-c:v", "ffv1", "-threads", "1", str(clip),
        ],
        cwd=tmp_path, capture_output=True, text=True, timeout=10,
    )
    assert extract.returncode == 0, extract.stderr
    role = (ROOT / "src.codex/skills/analyzing-video-bugs/SKILL.md").read_text(encoding="utf-8")
    recipe = next(command for command in re.findall(r"```bash\n(.*?)\n```", role, re.S)
                  if "native_%04d.png" in command)
    command = shlex.split(recipe.replace(chr(92) + "\n", " "))
    substitutions = {"<video>": str(clip), "<start>": "0", "<end>": "0.1"}
    for original, replacement in substitutions.items():
        command = [arg.replace(original, replacement) for arg in command]
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    timestamps = [float(value) for value in re.findall(r"pts_time:([0-9.]+)", result.stderr)]
    assert len(list(tmp_path.glob("native_*.png"))) == len(timestamps) == 6
    # A constant-rate extraction may hide this gap behind repeated/dropped output.
    assert timestamps == pytest.approx([0, 0.008, 0.017, 0.042, 0.05, 0.058], abs=0.001)
