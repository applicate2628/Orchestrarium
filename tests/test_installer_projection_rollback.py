"""No-follow rollback for a projection whose owned target was reclaimed."""
from pathlib import Path
import pytest
from test_hook_runtime_transactions import production_installer as installer

def test_owned_projection_reclaims_after_owned_target_inverse(tmp_path):
    anchor=tmp_path/'home';anchor.mkdir()
    source=tmp_path/'source';source.mkdir();(source/'SKILL.md').write_text('Synthetic skill.\n')
    provider=anchor/'.claude';provider.mkdir()
    with pytest.raises(RuntimeError, match='forced rollback'):
        with installer._InstallTransaction([provider,anchor/'.agents'],enabled=True) as tx:
            owner=installer._CreateOnlyMutablePath(anchor,tx,dry_run=False)
            canonical=owner.create_tree(Path('.agents/skills/example'),source)
            owner.create_projection(Path('.claude/skills/example'),canonical)
            raise RuntimeError('forced rollback')
    assert provider.is_dir() and list(provider.iterdir())==[]
    assert not (anchor/'.agents').exists()
