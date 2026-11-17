"""Keep the published transport manifest usable without launching a provider."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from _module_loading_support import load_module

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = load_module(
    ROOT / "scripts/validate-provider-prompt-projections.py",
    "sdk_transport_manifest_validator",
)
MANIFEST = ROOT / "shared/provider-prompt-projections.v1.json"


class SourceManifestTests(unittest.TestCase):
    def test_current_transport_sources_match_published_manifest(self):
        VALIDATOR.validate_source_manifest(MANIFEST, ROOT)

    def test_changed_source_digest_is_not_accepted(self):
        manifest = copy.deepcopy(json.loads(MANIFEST.read_bytes()))
        name = next(iter(manifest["files"]))
        manifest["files"][name]["sha256"] = "0" * 64
        scratch = ROOT / ".scratch"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="transport-manifest-", dir=scratch) as directory:
            path = Path(directory) / MANIFEST.name
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(VALIDATOR.ProjectionParityError, "digest drift"):
                VALIDATOR.validate_source_manifest(path, ROOT)


if __name__ == "__main__":
    unittest.main()
