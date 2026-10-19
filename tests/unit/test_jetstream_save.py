import unittest
import sys
import os
import types

# Ensure repository root is in sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Make the ansible-collection-style imports used by the source modules resolve
# to the in-repo plugins/ directory.  ``ansible_collections/`` is not tracked by
# git (it only held empty directories), so register the whole package chain as
# namespace packages in ``sys.modules``; this works even in a fresh checkout
# where ``ansible_collections/`` does not exist on disk.
_COLLECTION = "ansible_collections.lachlanstone.jetstream.plugins"
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

from plugins.module_utils.collector import ResultCollector
from plugins.modules.jetstream_save import save_configuration


class TestJetstreamSave(unittest.TestCase):
    def test_save_configuration_check_mode(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=True, verbosity=4)

        changed = save_configuration(
            net_connect=None,
            cmd="copy running-config startup-config",
            collector=collector,
            check_mode=True,
        )

        self.assertFalse(changed)
        steps = collector._steps
        self.assertEqual(len(steps), 1)
        self.assertFalse(steps[0]["changed"])
        self.assertEqual(steps[0]["command"], "copy running-config startup-config")
        self.assertIn("copy running-config startup-config", steps[0]["commands"])
        self.assertEqual(collector.return_info()["commands_sent"], [])

    def test_save_configuration_live_mode_custom_cmd(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=False)

        class FakeNetConnect:
            def __init__(self):
                self.saved_cmd = None

            def save_config(self, cmd):
                self.saved_cmd = cmd
                return "Building configuration... [OK]"

        fake_conn = FakeNetConnect()
        changed = save_configuration(
            net_connect=fake_conn,
            cmd="write",
            collector=collector,
            check_mode=False,
        )

        self.assertTrue(changed)
        self.assertEqual(fake_conn.saved_cmd, "write")
        steps = collector._steps
        self.assertEqual(len(steps), 1)
        self.assertTrue(steps[0]["changed"])
        self.assertEqual(steps[0]["command"], "write")
        self.assertEqual(steps[0]["stdout"], "Building configuration... [OK]")


if __name__ == "__main__":
    unittest.main()
