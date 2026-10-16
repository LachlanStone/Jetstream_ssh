import unittest
import unittest.mock as mock
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
        fake_conn.send_command.side_effect = [
            "raw textfsm",  # first call: textfsm
            "System Name - switch-01\nSystem Location - Core",  # second call: raw output
        ]

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
        self.assertEqual(len(res["stdout_lines"]), 2)
        self.assertEqual(res["parsed"]["System Name"], "switch-01")
        self.assertEqual(res["parsed"]["System Location"], "Core")
        fake_conn.enable.assert_called_once()


if __name__ == "__main__":
    unittest.main()
