import unittest
import unittest.mock as mock

from plugins.module_utils.collector import ResultCollector
from plugins.module_utils.interfaces.interface_builder import build_commands, _port_name
from plugins.module_utils.interfaces.interface_classes import (
    InterfaceConfig,
    RunningConfigInterface,
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

    def test_build_commands_acceptable_frame_type(self):
        tagged = build_commands({"name": "1/0/1", "acceptable_frame_type": "tagged"})
        self.assertIn("switchport acceptable frame tagged", tagged)

        all_frames = build_commands({"name": "1/0/1", "acceptable_frame_type": "all"})
        self.assertIn("switchport acceptable frame all", all_frames)

        omitted = build_commands({"name": "1/0/1"})
        self.assertTrue(
            all("acceptable-frame-type" not in c for c in omitted)
        )

    def test_configure_interface_check_mode(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=True)

        iface = {
            "name": "1/0/8",
            "enabled": False,
        }
        configure_interface(None, iface, collector, check_mode=True)

        step = collector._steps[-1]
        self.assertTrue(step["changed"])
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

    def test_noop_sends_nothing(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=False)

        iface = {
            "name": "1/0/1",
            "port_type": "gigabitEthernet",
            "speed": None,
            "enabled": None,
            "description": None,
            "pvid": None,
            "vlans_untagged": [],
            "vlans_tagged": [],
            "vlans_disabled": [],
            "acceptable_frame_type": "all",
        }
        config = InterfaceConfig("Tw1/0/1", "Enable", "Auto", "Auto", "Disable", "")
        running = RunningConfigInterface(
            name="1/0/1", port_type="gigabitEthernet"
        )

        configure_interface(
            None, iface, collector, check_mode=False, config=config, running=running
        )

        step = collector._steps[-1]
        self.assertFalse(step["changed"])
        self.assertEqual(step["commands"], [])

    def test_run_module_check_mode_skips_config_mode(self):
        module = mock.MagicMock()
        module.params = {
            "host": "192.0.2.10",
            "port": 22,
            "username": "admin",
            "password": "pw",
            "enable_password": "",
            "read_timeout": None,
            "interfaces": [
                {
                    "name": "1/0/1",
                    "port_type": "gigabitEthernet",
                    "speed": None,
                    "enabled": None,
                    "description": None,
                    "pvid": None,
                    "vlans_untagged": [],
                    "vlans_tagged": [],
                    "vlans_disabled": [],
                    "acceptable_frame_type": "all",
                }
            ],
        }
        module.check_mode = True
        module._verbosity = 0

        conn = mock.MagicMock()
        conn.__enter__.return_value = conn
        config = InterfaceConfig("Tw1/0/1", "Enable", "Auto", "Auto", "Disable", "")
        running = RunningConfigInterface(
            name="1/0/1", port_type="gigabitEthernet"
        )

        with mock.patch(
            "plugins.modules.jetstream_interfaces.ConnectHandler", return_value=conn
        ), mock.patch(
            "plugins.modules.jetstream_interfaces.get_interface_configuration",
            return_value=[config],
        ), mock.patch(
            "plugins.modules.jetstream_interfaces.get_running_config",
            return_value=[running],
        ):
            run_module(module)

        conn.config_mode.assert_not_called()
        module.exit_json.assert_called_once()


if __name__ == "__main__":
    unittest.main()
