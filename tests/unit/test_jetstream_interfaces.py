import unittest
import unittest.mock as mock

from plugins.module_utils.collector import ResultCollector
from plugins.module_utils.interfaces.interface_builder import (
    build_commands,
    _port_name,
    validate_vlans,
)
from plugins.modules.jetstream_interfaces import configure_interface, run_module


class TestJetstreamInterfaces(unittest.TestCase):
    def test_port_name(self):
        self.assertEqual(_port_name("1/0/1"), "gigabitEthernet 1/0/1")
        self.assertEqual(_port_name("1/0/1", "te"), "ten-gigabitEthernet 1/0/1")
        self.assertEqual(_port_name("fastEthernet 1/0/2"), "fastEthernet 1/0/2")
        with self.assertRaises(ValueError):
            _port_name("1/0/1", "invalid_type")

    def test_build_commands(self):
        iface = {
            "name": "1/0/5",
            "description": "Uplink",
            "enabled": True,
            "speed": "1000",
            "pvid": 100,
            "vlans_untagged": [100],
            "vlans_tagged": [200, 300],
        }
        cmds = build_commands(iface)
        self.assertEqual(cmds[0], "interface gigabitEthernet 1/0/5")
        self.assertIn("description Uplink", cmds)
        self.assertIn("no shutdown", cmds)
        self.assertIn("speed 1000", cmds)
        self.assertIn("switchport pvid 100", cmds)
        self.assertIn("switchport general allowed vlan 100 untagged", cmds)
        self.assertIn("switchport general allowed vlan 200,300 tagged", cmds)
        self.assertEqual(cmds[-1], "exit")

    def test_configure_interface_check_mode(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=True)

        iface = {
            "name": "1/0/8",
            "enabled": False,
        }
        configure_interface(None, iface, collector, check_mode=True)

        step = collector._steps[-1]
        self.assertFalse(step["changed"])
        self.assertIn("shutdown", step["commands"])
        self.assertEqual(step["name"], "configure_interface:1/0/8")

    def test_configure_interface_live_mode_mock(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=False)

        fake_conn = mock.MagicMock()
        fake_conn.send_command_timing.return_value = ""
        fake_conn.find_prompt.side_effect = [
            "switch(config)#",      # ensure_global_config
            "switch(config-if)#",   # after entering the interface
        ]

        iface = {
            "name": "1/0/1",
            "description": "Server Port",
        }
        with mock.patch("plugins.modules.jetstream_interfaces.send_command", return_value=""):
            configure_interface(fake_conn, iface, collector, check_mode=False)

        self.assertTrue(collector.changed)
        step = collector._steps[-1]
        self.assertTrue(step["changed"])
        self.assertIn("interface gigabitEthernet 1/0/1", step["commands"])

    def test_validate_vlans_accepts_distinct_vlans(self):
        validate_vlans({
            "name": "1/0/1",
            "vlans_untagged": [10],
            "vlans_tagged": [20, 30],
            "vlans_disabled": [40],
        })
        validate_vlans({"name": "1/0/1"})

    def test_validate_vlans_rejects_tagged_and_untagged(self):
        iface = {"name": "1/0/1", "vlans_untagged": [10], "vlans_tagged": [10, 20]}
        with self.assertRaises(ValueError) as ctx:
            validate_vlans(iface)
        self.assertIn("1/0/1", str(ctx.exception))
        self.assertIn("[10]", str(ctx.exception))

    def test_validate_vlans_rejects_disabled_overlap(self):
        with self.assertRaises(ValueError):
            validate_vlans({"name": "1/0/1", "vlans_tagged": [20], "vlans_disabled": [20]})

    def test_validate_vlans_rejects_duplicate_within_list(self):
        with self.assertRaises(ValueError):
            validate_vlans({"name": "1/0/1", "vlans_tagged": [20, 20]})

    def test_run_module_fails_before_connecting(self):
        module = mock.MagicMock()
        module.params = {
            "host": "192.0.2.10",
            "interfaces": [
                {"name": "1/0/1", "vlans_untagged": [10], "vlans_tagged": [10]},
            ],
        }
        with mock.patch("plugins.modules.jetstream_interfaces.build_device", return_value={}), \
                mock.patch("plugins.modules.jetstream_interfaces.ConnectHandler") as connect:
            with self.assertRaises(ValueError):
                run_module(module)
        connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
