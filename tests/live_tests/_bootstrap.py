"""Make ``ansible_collections.lachlanstone.jetstream.plugins`` importable from the repo's ``plugins/``.

Import this module before any ``ansible_collections...`` import.  It registers the
package chain in ``sys.modules`` so no on-disk ``ansible_collections/`` tree is needed.
"""

import os
import sys
import types

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

_COLLECTION = "ansible_collections.lachlanstone.jetstream.plugins"
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
sys.modules[_COLLECTION].__path__ = [os.path.join(REPO_ROOT, "plugins")]
