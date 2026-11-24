"""Real root-input disappearance must never become approved initial absence."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "project_root_observation_owner", ROOT / "scripts" / "mutate-work-item.py"
)
assert SPEC and SPEC.loader
owner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = owner
SPEC.loader.exec_module(owner)


class ProjectRootObservationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="project-root-observation-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def create(self, path, kind):
        if kind == "file":
            path.write_bytes(b"Current selected input.\n")
        else:
            path.mkdir()
            (path / "member.txt").write_bytes(b"Current namespace member.\n")

    def observe(self, path, kind, evidence):
        if kind == "namespace":
            return owner._project_identity_children_at(path, evidence, "WI-README-STALE")
        return owner._observe_project_path_at(path, kind, evidence, "WI-README-STALE")

    def test_disappearance_after_first_presence_is_not_initial_absence(self):
        for kind in ("file", "directory", "namespace"):
            with self.subTest(kind=kind):
                selected = self.root / kind
                held = self.root / (kind + "-held")
                self.create(selected, kind)
                original = Path.lstat
                observed = []
                evidence = []

                def disappear(path, *args, **kwargs):
                    result = original(path, *args, **kwargs)
                    if path == selected and not observed:
                        selected.rename(held)
                        observed.append(result)
                    return result

                with patch.object(Path, "lstat", disappear):
                    with self.assertRaises(owner.LifecycleError):
                        self.observe(selected, kind, evidence)
                self.assertEqual(len(observed), 1)
                self.assertEqual(owner._lifecycle_file_identity(held.lstat()),
                                 owner._lifecycle_file_identity(observed[0]))
                self.assertFalse(selected.exists())
                self.assertFalse(any(tag == "absent" for tag, _value in evidence))

    def test_initial_absence_stays_bound_and_rejects_later_appearance(self):
        for kind in ("file", "directory", "namespace"):
            with self.subTest(kind=kind):
                selected = self.root / kind
                evidence = []
                self.assertEqual(self.observe(selected, kind, evidence),
                                 () if kind == "namespace" else None)
                owner._verify_project_binding_evidence(tuple(evidence), "WI-README-STALE")
                self.create(selected, kind)
                with self.assertRaises(owner.LifecycleError):
                    owner._verify_project_binding_evidence(tuple(evidence), "WI-README-STALE")
                self.assertTrue(selected.exists())

    def test_present_input_rejects_later_same_content_replacement(self):
        for kind in ("file", "directory", "namespace"):
            with self.subTest(kind=kind):
                selected = self.root / kind
                held = self.root / (kind + "-held")
                self.create(selected, kind)
                evidence = []
                self.observe(selected, kind, evidence)
                owner._verify_project_binding_evidence(tuple(evidence), "WI-README-STALE")
                original = owner._lifecycle_file_identity(selected.lstat())
                selected.rename(held)
                self.create(selected, kind)
                with self.assertRaises(owner.LifecycleError):
                    owner._verify_project_binding_evidence(tuple(evidence), "WI-README-STALE")
                self.assertEqual(owner._lifecycle_file_identity(held.lstat()), original)
                self.assertTrue(selected.exists())


if __name__ == "__main__":
    unittest.main()
