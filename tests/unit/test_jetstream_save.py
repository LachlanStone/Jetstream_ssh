import unittest

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
