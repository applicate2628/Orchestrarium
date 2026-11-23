"""A version label alone must not be a runtime parser-compatibility gate."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_private_package_version_labels_are_not_runtime_gate():
    probe = """
import importlib, sys
sys.path.insert(0, sys.argv[1])
import installer_markdown, markdown_it, mdurl
markdown_it.__version__ = 'synthetic-label'
mdurl.__version__ = 'synthetic-label'
importlib.reload(installer_markdown)
source = 'before `protected` after'
visible, spans = installer_markdown.document_context(source)
assert spans == [(7, 18)]
assert visible == 'before             after'
"""
    result = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", probe,
                             str(ROOT / "scripts")], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
