"""Source-installer composition root for the private Markdown dependency."""
from pathlib import Path
from importlib.machinery import PathFinder
from importlib.util import module_from_spec
import sys


_VENDOR = Path(__file__).resolve().parent / "vendor"


def _check_package_origins() -> None:
    for name, module in tuple(sys.modules.items()):
        if name in ("markdown_it", "mdurl") or name.startswith(("markdown_it.", "mdurl.")):
            filename = getattr(module, "__file__", None)
            tree = _VENDOR / ("markdown_it" if name == "markdown_it" or name.startswith("markdown_it.") else "mdurl")
            if not filename or not Path(filename).resolve().is_relative_to(tree):
                raise RuntimeError("E_INSTALLER_MARKDOWN_SUPPLY: foreign package origin")
            locations = getattr(module, "__path__", ())
            if any(not Path(location).resolve().is_relative_to(tree) for location in locations):
                raise RuntimeError("E_INSTALLER_MARKDOWN_SUPPLY: foreign package search path")


def _private_spec(name):
    tree = _VENDOR / name
    spec = PathFinder.find_spec(name, [str(_VENDOR)])
    if (spec is None or spec.loader is None or spec.origin is None
            or Path(spec.origin).resolve() != tree / "__init__.py"
            or spec.submodule_search_locations is None
            or [Path(location).resolve() for location in spec.submodule_search_locations] != [tree]):
        raise RuntimeError("E_INSTALLER_MARKDOWN_SUPPLY: missing or invalid private package")
    return spec


def _initialize_private(name, spec):
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    module = module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        if sys.modules.get(name) is module:
            del sys.modules[name]
        raise
    return module


_check_package_origins()
# Resolve both packages against only the private directory before either can
# execute. A missing package cannot fall through to ambient import search.
_mdurl_spec = _private_spec("mdurl")
_markdown_spec = _private_spec("markdown_it")
mdurl = _initialize_private("mdurl", _mdurl_spec)
markdown_it = _initialize_private("markdown_it", _markdown_spec)

_check_package_origins()
if markdown_it.__version__ != "4.0.0" or mdurl.__version__ != "0.1.2":
    raise RuntimeError("E_INSTALLER_MARKDOWN_SUPPLY: package version")

from .context import document_context

__all__ = ("document_context",)
