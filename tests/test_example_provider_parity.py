from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_PROVIDER_ROOTS = {
    "gemini": ROOT / "src.gemini",
    "qwen": ROOT / "src.qwen",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_example_provider_leads_preserve_task_memory_bootstrap_invariant():
    for provider, root in EXAMPLE_PROVIDER_ROOTS.items():
        text = _read(root / "skills" / "lead" / "SKILL.md")
        assert "work-items/active/<date>-<slug>/" in text, provider
        assert "no local init" in text, provider
        assert "Do not treat" in text, provider


def test_example_provider_product_managers_preserve_epic_admission_invariant():
    for provider, root in EXAMPLE_PROVIDER_ROOTS.items():
        text = _read(root / "skills" / "product-manager" / "SKILL.md")
        assert "No-epic rationale:" in text, provider
        assert "multiple related work-items" in text, provider


def test_example_provider_reference_docs_keep_shared_global_demo_fallback():
    docs = _read(ROOT / "docs" / "agents-mode-reference.md")
    for provider in ("Gemini", "Qwen"):
        assert provider in docs
    assert "global `~/.qwen/.agents-mode.yaml`, global legacy `~/.qwen/.agents-mode`, then the shared cross-pack global" in docs
    assert "global `~/.gemini/.agents-mode.yaml`, then global legacy `~/.gemini/.agents-mode`, then the shared cross-pack global" in docs
