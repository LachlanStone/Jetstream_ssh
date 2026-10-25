import sys
import os
import types

# Ensure repository root is in sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Ensure tests/live_tests is importable for shared test helpers
_LIVE_TESTS = os.path.join(REPO_ROOT, "tests", "live_tests")
if _LIVE_TESTS not in sys.path:
    sys.path.insert(0, _LIVE_TESTS)

# Make the ansible-collection-style imports used by the source modules resolve
# to the in-repo plugins/ directory.  ``ansible_collections/`` is not tracked by
# git (it only held empty directories), so register the whole package chain as
# namespace packages in ``sys.modules``; this works even in a fresh checkout
# where ``ansible_collections/`` does not exist on disk.
_COLLECTION = "plugins"
_REAL_PLUGINS = os.path.join(REPO_ROOT, "plugins")
for _pkg in (
    "ansible_collections",
    "ansible_collections.lachlanstone",
    "ansible_collections.lachlanstone.jetstream",
    _COLLECTION,
):
    if _pkg not in sys.modules:
        _m = types.ModuleType(_pkg)
        _m.__path__ = []
        sys.modules[_pkg] = _m
sys.modules[_COLLECTION].__path__ = [_REAL_PLUGINS]
# Source modules import their siblings through the full collection path, e.g.
# ``ansible_collections.lachlanstone.jetstream.plugins.module_utils...``.
# Point the collection package at the repo root so that nested ``plugins``
# package resolves too.
sys.modules["ansible_collections.lachlanstone.jetstream"].__path__ = [REPO_ROOT]
