import unittest
import unittest.mock as mock

from plugins.module_utils.collector import ResultCollector
from plugins.module_utils.vlans.vlan_builder import build_vlan_commands
from plugins.modules.jetstream_vlans import configure_vlan


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


class TestJetstreamVlans(unittest.TestCase):
    def test_configure_vlan_check_mode(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=True)

        vlan = {"vlan_id": 10, "name": "Servers"}
        configure_vlan(None, vlan, collector, check_mode=True)

        step = collector._steps[-1]
        self.assertFalse(step["changed"])
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


if __name__ == "__main__":
    unittest.main()
