import unittest
import unittest.mock as mock

from plugins.module_utils.collector import ResultCollector
from plugins.module_utils.vlans.vlan_builder import build_vlan_commands, build_vlan_delta
from plugins.module_utils.vlans.vlan_parsers import (
    get_current_vlans,
    parse_running_config_vlans,
)
from plugins.modules.jetstream_vlans import configure_vlan, run_module


class TestVlanBuilder(unittest.TestCase):
    def test_name_and_static_svi(self):
        cmds = build_vlan_commands({
            "vlan_id": 10,
            "name": "Servers",
            "ip_address": "192.168.10.1",
            "subnet_mask": "255.255.255.0",
            "ip_dhcp": False,
        })
        self.assertEqual(
            cmds,
            [
                "vlan 10",
                "name Servers",
                "exit",
                "interface vlan 10",
                "ip address 192.168.10.1 255.255.255.0",
                "exit",
            ],
        )

    def test_name_without_svi(self):
        cmds = build_vlan_commands({
            "vlan_id": 20,
            "name": "Clients",
            "ip_address": None,
            "subnet_mask": None,
            "ip_dhcp": False,
        })
        self.assertEqual(cmds, ["vlan 20", "name Clients", "exit"])

    def test_dhcp_svi_without_name(self):
        cmds = build_vlan_commands({
            "vlan_id": 30,
            "name": None,
            "ip_address": None,
            "subnet_mask": None,
            "ip_dhcp": True,
        })
        self.assertEqual(
            cmds,
            ["vlan 30", "exit", "interface vlan 30", "ip address-alloc dhcp", "exit"],
        )

    def test_bare_vlan(self):
        cmds = build_vlan_commands({
            "vlan_id": 40,
            "name": None,
            "ip_address": None,
            "subnet_mask": None,
            "ip_dhcp": False,
        })
        self.assertEqual(cmds, ["vlan 40", "exit"])

    def test_deterministic(self):
        vlan = {"vlan_id": 10, "name": "Servers"}
        self.assertEqual(build_vlan_commands(vlan), build_vlan_commands(vlan))

    def test_vlan_id_out_of_range(self):
        with self.assertRaises(ValueError):
            build_vlan_commands({"vlan_id": 0})
        with self.assertRaises(ValueError):
            build_vlan_commands({"vlan_id": 4095})

    def test_vlan_id_missing_or_invalid_type(self):
        with self.assertRaises(ValueError):
            build_vlan_commands({})
        with self.assertRaises(ValueError):
            build_vlan_commands({"vlan_id": "10"})
        with self.assertRaises(ValueError):
            build_vlan_commands({"vlan_id": None})
        with self.assertRaises(ValueError):
            build_vlan_commands({"vlan_id": True})

    def test_ip_address_and_dhcp_are_mutually_exclusive(self):
        with self.assertRaises(ValueError):
            build_vlan_commands({
                "vlan_id": 10,
                "ip_address": "192.168.10.1",
                "subnet_mask": "255.255.255.0",
                "ip_dhcp": True,
            })

    def test_ip_address_requires_subnet_mask(self):
        with self.assertRaises(ValueError):
            build_vlan_commands({"vlan_id": 10, "ip_address": "192.168.10.1"})

    def test_delta_none_when_matching(self):
        vlan = {
            "vlan_id": 10,
            "name": "Servers",
            "ip_address": "192.168.10.1",
            "subnet_mask": "255.255.255.0",
            "ip_dhcp": False,
        }
        self.assertIsNone(build_vlan_delta(vlan, dict(vlan)))

    def test_delta_only_changed_svi(self):
        vlan = {
            "vlan_id": 10,
            "name": "Servers",
            "ip_address": "192.168.10.2",
            "subnet_mask": "255.255.255.0",
            "ip_dhcp": False,
        }
        current = dict(vlan, ip_address="192.168.10.1")
        self.assertEqual(
            build_vlan_delta(vlan, current),
            {
                "vlan_id": 10,
                "ip_address": "192.168.10.2",
                "subnet_mask": "255.255.255.0",
            },
        )


class TestVlanParsers(unittest.TestCase):
    SAMPLE = """\
vlan 1
 name "System-VLAN"
#
vlan 10-11
#
interface vlan 1
  ip address-alloc dhcp
  ipv6 enable
#
interface vlan 10
  ip address 10.10.10.50 255.255.255.0
  no ipv6 enable
#
"""

    def test_parse_vlan_and_svi_state(self):
        parsed = parse_running_config_vlans(self.SAMPLE)

        self.assertEqual(parsed[1]["name"], "System-VLAN")
        self.assertTrue(parsed[1]["ip_dhcp"])
        self.assertEqual(parsed[10]["ip_address"], "10.10.10.50")
        self.assertEqual(parsed[10]["subnet_mask"], "255.255.255.0")
        self.assertIn(11, parsed)
        self.assertIsNone(parsed[11]["name"])

    def test_parser_to_delta_end_to_end(self):
        parsed = parse_running_config_vlans(self.SAMPLE)
        matching = {
            "vlan_id": 10,
            "name": None,
            "ip_address": "10.10.10.50",
            "subnet_mask": "255.255.255.0",
            "ip_dhcp": False,
        }
        self.assertIsNone(build_vlan_delta(matching, parsed[10]))

        drift = dict(matching, ip_address="10.10.10.99")
        self.assertEqual(
            build_vlan_delta(drift, parsed[10])["ip_address"], "10.10.10.99"
        )

    def test_get_current_vlans_rejects_empty_output(self):
        with mock.patch(
            "plugins.module_utils.vlans.vlan_parsers.send_command", return_value=""
        ):
            with self.assertRaisesRegex(RuntimeError, "refusing to apply"):
                get_current_vlans(None)


class TestJetstreamVlans(unittest.TestCase):
    def test_configure_vlan_check_mode(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=True)

        vlan = {"vlan_id": 10, "name": "Servers"}
        configure_vlan(None, vlan, collector, check_mode=True)

        step = collector._steps[-1]
        self.assertTrue(step["changed"])
        self.assertEqual(step["name"], "configure_vlan:10")
        self.assertEqual(step["commands"], ["vlan 10", "name Servers", "exit"])
        self.assertEqual(step["settings"], {"name": "Servers"})

    def test_configure_vlan_live_mode_mock(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=False)

        fake_conn = mock.MagicMock()
        fake_conn.send_command_timing.return_value = ""
        fake_conn.find_prompt.side_effect = [
            "switch(config)#",      # ensure_global_config
            "switch(config-vlan)#", # after entering the VLAN context
        ]

        vlan = {"vlan_id": 10, "name": "Servers"}
        with mock.patch("plugins.modules.jetstream_vlans.send_command", return_value=""):
            configure_vlan(fake_conn, vlan, collector, check_mode=False)

        self.assertTrue(collector.changed)
        step = collector._steps[-1]
        self.assertTrue(step["changed"])
        self.assertEqual(step["commands"], ["vlan 10", "name Servers", "exit"])
        self.assertEqual(fake_conn.send_command_timing.call_count, 1)

    def test_run_module_empty_vlans(self):
        fake_module = mock.MagicMock()
        fake_module.params = {
            "host": "192.0.2.10",
            "port": 22,
            "username": "admin",
            "password": "pw",
            "enable_password": "",
            "read_timeout": None,
            "vlans": [],
        }
        fake_module.check_mode = False
        fake_module._verbosity = 0

        with mock.patch("plugins.modules.jetstream_vlans.ConnectHandler") as mock_connect:
            run_module(fake_module)

        mock_connect.assert_not_called()
        fake_module.exit_json.assert_called_once()
        kwargs = fake_module.exit_json.call_args.kwargs
        self.assertFalse(kwargs["changed"])
        self.assertIsNone(kwargs["current_state"])

    def test_configure_vlan_noop_sends_nothing(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=False)

        vlan = {"vlan_id": 10, "name": "Servers"}
        current = {
            "vlan_id": 10,
            "name": "Servers",
            "ip_address": None,
            "subnet_mask": None,
            "ip_dhcp": False,
        }
        configure_vlan(None, vlan, collector, check_mode=False, current=current)

        step = collector._steps[-1]
        self.assertFalse(step["changed"])
        self.assertEqual(step["commands"], [])

    def test_run_module_check_mode_skips_config_mode(self):
        fake_module = mock.MagicMock()
        fake_module.params = {
            "host": "192.0.2.10",
            "port": 22,
            "username": "admin",
            "password": "pw",
            "enable_password": "",
            "read_timeout": None,
            "vlans": [
                {
                    "vlan_id": 10,
                    "name": "Servers",
                    "ip_address": None,
                    "subnet_mask": None,
                    "ip_dhcp": False,
                }
            ],
        }
        fake_module.check_mode = True
        fake_module._verbosity = 0

        fake_conn = mock.MagicMock()
        fake_conn.__enter__.return_value = fake_conn

        with mock.patch(
            "plugins.modules.jetstream_vlans.ConnectHandler", return_value=fake_conn
        ), mock.patch(
            "plugins.modules.jetstream_vlans.get_current_vlans", return_value={}
        ):
            run_module(fake_module)

        fake_conn.config_mode.assert_not_called()
        fake_module.exit_json.assert_called_once()


if __name__ == "__main__":
    unittest.main()
