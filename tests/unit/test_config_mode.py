import unittest
import unittest.mock as mock

from netmiko.base_connection import BaseConnection

from plugins.module_utils.config_mode import (
    ensure_global_config,
    get_config_mode,
    is_in_config_interface,
    parse_config_mode,
    require_config_mode,
)


class TestParseConfigMode(unittest.TestCase):
    def test_modes(self):
        cases = {
            "switch(config)#": "global",
            "switch(config-vlan)#": "vlan",
            "switch(config-if)#": "interface",
            "switch(config-if-range)#": "interface-range",
            "switch#": "privileged",
            "switch>": "user",
            "unexpected": "unknown",
        }
        for prompt, expected in cases.items():
            self.assertEqual(parse_config_mode(prompt), expected, prompt)


class TestConnectionHelpers(unittest.TestCase):
    def test_ensure_global_config_waits_for_fragmented_prompt(self):
        class FragmentedConnection:
            RETURN = "\n"
            RESPONSE_RETURN = "\n"
            read_timeout_override = None
            _read_buffer = ""
            find_prompt = BaseConnection.find_prompt
            read_until_pattern = BaseConnection.read_until_pattern

            def __init__(self):
                self.chunks = iter(["switch(config", ")#"])

            def select_delay_factor(self, delay_factor):
                return delay_factor

            def clear_buffer(self):
                pass

            def write_channel(self, data):
                pass

            def read_channel(self):
                return next(self.chunks)

        with mock.patch("netmiko.base_connection.time.sleep"):
            self.assertEqual(ensure_global_config(FragmentedConnection()), "global")

    def test_is_in_config_interface(self):
        conn = mock.MagicMock()
        conn.find_prompt.return_value = "switch(config-if)#"
        self.assertTrue(is_in_config_interface(conn))

        conn.find_prompt.return_value = "switch(config)#"
        self.assertFalse(is_in_config_interface(conn))

    def test_require_config_mode_raises(self):
        conn = mock.MagicMock()
        conn.find_prompt.return_value = "switch(config)#"
        with self.assertRaises(RuntimeError):
            require_config_mode(conn, "interface", context="Interface 1/0/1")

    def test_require_config_mode_waits_for_prompt_update(self):
        conn = mock.MagicMock()
        conn.find_prompt.side_effect = [
            "switch(config)#",
            "switch(config-vlan)#",
        ]

        with mock.patch("plugins.module_utils.config_mode.time.sleep"):
            require_config_mode(conn, "vlan", context="VLAN 10")

        self.assertEqual(conn.find_prompt.call_count, 2)

    def test_ensure_global_config_exits_submode(self):
        conn = mock.MagicMock()
        conn.find_prompt.side_effect = [
            "switch(config-if)#",
            "switch(config)#",
        ]

        ensure_global_config(conn)

        conn.send_command_timing.assert_called_once_with("exit")

    def test_ensure_global_config_raises_outside_config(self):
        conn = mock.MagicMock()
        conn.find_prompt.return_value = "switch#"
        with self.assertRaises(RuntimeError):
            ensure_global_config(conn)


if __name__ == "__main__":
    unittest.main()
