import unittest
from unittest.mock import MagicMock, patch

from plugins.module_utils.collector import ResultCollector
from plugins.modules.jetstream_save import run_module, save_configuration


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

    def test_run_module_check_mode_does_not_connect(self):
        module = MagicMock()
        module.params = {
            "host": "192.0.2.10",
            "port": 22,
            "username": "admin",
            "password": "pw",
            "enable_password": "",
            "read_timeout": None,
            "command": "copy running-config startup-config",
        }
        module.check_mode = True
        module._verbosity = 0

        with patch(
            "plugins.modules.jetstream_save.build_device", return_value={}
        ), patch("plugins.modules.jetstream_save.ConnectHandler") as connect:
            run_module(module)

        connect.assert_not_called()
        module.exit_json.assert_called_once()


if __name__ == "__main__":
    unittest.main()
