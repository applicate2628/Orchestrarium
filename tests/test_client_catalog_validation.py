"""Inspect the single declared catalog without executing installer code."""
from pathlib import Path
import shutil
from _module_loading_support import load_module
ROOT=Path(__file__).resolve().parents[1]
RUNTIME=load_module(ROOT/'scripts/skill_pack_validator_runtime.py','catalog_validation_runtime')


def fixture(tmp_path):
    for name in ['install.py','scripts/installation/clients.py']:
        target=tmp_path/name; target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/name,target)
    return tmp_path


def test_current_root_uses_declarative_catalog_without_importing(tmp_path):
    root=fixture(tmp_path)
    assert RUNTIME.installer_choices_are_supported_production_packs(root)


def test_catalog_dynamic_call_is_not_executed(tmp_path):
    root=fixture(tmp_path)
    (root/'scripts/installation/clients.py').write_text('CLIENTS = load_remote_clients()\n')
    assert not RUNTIME.installer_choices_are_supported_production_packs(root)


def test_second_primary_is_not_admitted(tmp_path):
    root=fixture(tmp_path);path=root/'scripts/installation/clients.py'
    path.write_text(path.read_text().replace('"primary": False','"primary": True'))
    assert not RUNTIME.installer_choices_are_supported_production_packs(root)


def test_arbitrary_root_computation_is_not_admitted(tmp_path):
    root=fixture(tmp_path);path=root/'install.py'
    path.write_text(path.read_text().replace('CLIENTS = tuple((name, spec["label"]) for name, spec in CLIENT_CATALOG.items())','CLIENTS = load_remote_clients()'))
    assert not RUNTIME.installer_choices_are_supported_production_packs(root)
