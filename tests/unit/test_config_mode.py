import unittest
import unittest.mock as mock

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
