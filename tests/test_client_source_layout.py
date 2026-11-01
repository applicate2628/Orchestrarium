"""Source layout keeps one primary host and secondary adapters, not products."""
from pathlib import Path
from _module_loading_support import load_module
ROOT = Path(__file__).resolve().parents[1]
CLIENTS = load_module(ROOT/'scripts/installation/clients.py','source_layout_clients').CLIENTS


def test_primary_and_secondary_source_roots_are_explicit():
    assert CLIENTS['codex']['primary'] is True
    assert CLIENTS['codex']['source_root'] == 'src.codex'
    assert CLIENTS['claude']['primary'] is False
    assert CLIENTS['claude']['source_root'] == 'adapters/claude'
    assert CLIENTS['claude']['references_root'] == 'adapters/claude/references'
    for client in CLIENTS.values():
        assert (ROOT/client['source_root']).is_dir()
        assert (ROOT/client['references_root']).is_dir()
    assert not (ROOT/'src.claude').exists()
    assert not (ROOT/'references-claude').exists()


def test_common_bundle_includes_secondary_adapters_once():
    build=load_module(ROOT/'scripts/distribution/build.py','source_layout_builder')
    assert 'adapters' in build.APP_INPUTS
    assert 'src.claude' not in build.APP_INPUTS
    assert 'references-claude' not in build.APP_INPUTS


def test_current_extraction_does_not_drop_secondary_adapter():
    extract=load_module(ROOT/'scripts/extract-provider-branch.py','source_layout_extract')
    assert extract.include_from_main('adapters/claude/agents/lead.md','claude')
    assert extract.include_from_main('adapters/claude/references/README.md','claude')
    assert not extract.include_from_main('adapters/claude/agents/lead.md','codex')


def test_relocation_preserves_runtime_enum_scan_scope():
    validate=load_module(ROOT/'scripts/validate-agents-mode-contract.py','source_layout_enum_contract')
    paths=validate._iter_enum_scan_files(ROOT)
    refs=ROOT/'adapters/claude/references'
    assert not any(path.is_relative_to(refs) for path in paths)
    assert ROOT/'adapters/claude/CLAUDE.md' in paths
    assert any(path.is_relative_to(ROOT/'shared/references') for path in paths)
