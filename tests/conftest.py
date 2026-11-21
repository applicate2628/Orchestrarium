"""Shared fixtures for suites that import publication modules in-process."""

import sys

import pytest


@pytest.fixture(scope="module")
def isolated_standalone_review_modules():
    # Standalone scanner imports may leave these slots populated. In native
    # gate execution those slots must be empty before the captured load.
    names = (
        "_orchestrarium_publication_review_policy_v1",
        "_orchestrarium_linked_runtime_subroots_v1",
    )
    saved = {name: sys.modules[name] for name in names if name in sys.modules}
    try:
        yield
    finally:
        for name in names:
            if name in saved:
                sys.modules[name] = saved[name]
            else:
                sys.modules.pop(name, None)
