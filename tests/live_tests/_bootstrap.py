"""Put the repo root on ``sys.path`` so ``plugins.*`` and ``ansible_collections.*`` resolve.

Import this module before any ``plugins...`` or ``ansible_collections...`` import.
"""

import os
import sys
import types

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Source modules import their siblings through the full collection path, e.g.
# ``ansible_collections.lachlanstone.jetstream.plugins.module_utils...``.
# ``ansible_collections/`` is not present in a checkout (only the leaf repo is),
# so register the package chain as namespace packages pointing at this repo —
# the same trick ``tests/unit/conftest.py`` uses for pytest.
for _pkg in (
    "ansible_collections",
    "ansible_collections.lachlanstone",
    "ansible_collections.lachlanstone.jetstream",
):
    if _pkg not in sys.modules:
        _mod = types.ModuleType(_pkg)
        _mod.__path__ = []
        sys.modules[_pkg] = _mod
sys.modules["ansible_collections.lachlanstone.jetstream"].__path__ = [REPO_ROOT]
