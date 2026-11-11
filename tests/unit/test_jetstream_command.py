import unittest
import unittest.mock as mock

from plugins.modules.jetstream_command import parse_output, send_commands


class TestJetstreamCommand(unittest.TestCase):
    def test_parse_output(self):
        sample = """
System Description - TP-Link JetStream Switch
System Up Time     - 10 days, 4 hours
Firmware Version   - 1.0.0
Random Line Without Dash
"""
        parsed = parse_output(sample)
        self.assertEqual(parsed["System Description"], "TP-Link JetStream Switch")
        self.assertEqual(parsed["System Up Time"], "10 days, 4 hours")
        self.assertEqual(parsed["Firmware Version"], "1.0.0")
        self.assertNotIn("Random Line Without Dash", parsed)

    def test_send_commands_mock(self):
        fake_conn = mock.MagicMock()
        fake_conn.__enter__.return_value = fake_conn
        fake_conn.device_type = "tplink_jetstream"
        fake_conn.send_command.return_value = "System Name - switch-01\nSystem Location - Core"

        params = {
            "host": "192.0.2.10",
            "port": 22,
            "username": "admin",
            "password": "pwd",
            "enable_password": "pwd",
            "command_level": "enable",
            "command": "show system-info",
            "commands": None,
        }

        with mock.patch("plugins.modules.jetstream_command.ConnectHandler", return_value=fake_conn):
            results = send_commands(params)

        self.assertEqual(len(results), 1)
        res = results[0]
        self.assertEqual(res["command"], "show system-info")
        self.assertIn("System Name", res["stdout"])
        self.assertEqual(res["textfsm_parsed"], "System Name - switch-01\nSystem Location - Core")
        self.assertEqual(len(res["stdout_lines"]), 2)
        self.assertEqual(res["parsed"]["System Name"], "switch-01")
        self.assertEqual(res["parsed"]["System Location"], "Core")
        fake_conn.enable.assert_called_once()
        fake_conn.send_command.assert_called_once()
        fake_conn.send_command.assert_called_once_with("show system-info", auto_find_prompt=True)

    def test_send_multiple_commands_mock(self):
        fake_conn = mock.MagicMock()
        fake_conn.__enter__.return_value = fake_conn
        fake_conn.device_type = "tplink_jetstream"
        fake_conn.send_command.side_effect = [
            "System Name - switch-01\nSystem Location - Core",
            "VLAN 10 Active",
        ]

        params = {
            "host": "192.0.2.10",
            "port": 22,
            "username": "admin",
            "password": "pwd",
            "enable_password": "pwd",
            "command_level": "cli",
            "command": None,
            "commands": ["show system-info", "show vlan"],
        }

        with mock.patch("plugins.modules.jetstream_command.ConnectHandler", return_value=fake_conn):
            results = send_commands(params)

        self.assertEqual(len(results), 2)
        self.assertEqual(fake_conn.send_command.call_count, 2)
        self.assertEqual(results[0]["stdout"], "System Name - switch-01\nSystem Location - Core")
        self.assertEqual(results[1]["stdout"], "VLAN 10 Active")

if __name__ == "__main__":
    unittest.main()
