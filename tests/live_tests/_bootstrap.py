"""Put the repo root on ``sys.path`` so ``plugins.*`` is importable.

Import this module before any ``plugins...`` import.
"""

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
