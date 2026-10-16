import unittest
import sys
import os
import types

# Ensure repository root is in sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Make the ansible-collection-style imports used by the source modules resolve
# to the in-repo plugins/ package (ansible_collections/... is empty in this checkout).
_COLLECTION = "ansible_collections.lachlanstone.jetstream.plugins"
if _COLLECTION not in sys.modules:
    _collection_pkg = types.ModuleType(_COLLECTION)
    _collection_pkg.__path__ = [os.path.join(REPO_ROOT, "plugins")]
    sys.modules[_COLLECTION] = _collection_pkg

from plugins.module_utils.collector import ResultCollector
from plugins.modules.jetstream_save import save_configuration


class TestJetstreamSave(unittest.TestCase):
    def test_save_configuration_check_mode(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=True)

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
