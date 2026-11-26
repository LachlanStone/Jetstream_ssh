"""Unit tests for jetstream_interfaces_v2 idempotent diffing."""

import unittest
from unittest.mock import MagicMock, patch

from plugins.module_utils.collector import ResultCollector
from plugins.module_utils.interfaces.interface_classes import (
    InterfaceConfig,
    RunningConfigInterface,
    _port_id,
    diff_interface,
)
from plugins.module_utils.interfaces.interface_parsers import parse_running_config
from plugins.modules.jetstream_interfaces_v2 import configure_interface, run_module


def _desired(overrides=None):
    """Return a full interface entry with the Ansible-applied defaults."""
    entry = {
        "name": "1/0/1",
        "port_type": "two-gigabitEthernet",
        "speed": None,
        "enabled": None,
        "description": None,
        "pvid": None,
        "vlans_untagged": [],
        "vlans_tagged": [],
        "vlans_disabled": [],
        "acceptable_frame_type": None,
    }
    if overrides:
        entry.update(overrides)
    return entry


class TestPortId(unittest.TestCase):
    def test_normalisation(self):
        self.assertEqual(_port_id("1/0/1"), "1/0/1")
        self.assertEqual(_port_id("Tw1/0/1"), "1/0/1")
        self.assertEqual(_port_id("Te1/0/25"), "1/0/25")
        self.assertEqual(_port_id("two-gigabitEthernet 1/0/1"), "1/0/1")


class TestDiffInterface(unittest.TestCase):
    def test_match_returns_none(self):
        desired = _desired({
            "speed": "auto",
            "enabled": True,
            "description": "Uplink",
            "pvid": 10,
            "vlans_untagged": [10],
            "vlans_tagged": [20, 30],
            "acceptable_frame_type": "all",
        })
        config = InterfaceConfig("Tw1/0/1", "Enable", "Auto", "Auto", "Disable", "Uplink")
        running = RunningConfigInterface(
            name="1/0/1",
            port_type="two-gigabitEthernet",
            description="Uplink",
            pvid=10,
            vlans_untagged=[10],
            vlans_tagged=[30, 20],  # order-insensitive
            acceptable_frame_type="all",
        )
        self.assertIsNone(diff_interface(desired, config, running))

    def test_drift_returns_exact_delta(self):
        desired = _desired({
            "speed": "1000",
            "enabled": False,
            "description": "Server Port",
            "pvid": 20,
            "vlans_untagged": [20],
            "vlans_tagged": [30],
            "vlans_disabled": [40],
            "acceptable_frame_type": "tagged",
        })
        config = InterfaceConfig("Tw1/0/1", "Enable", "Auto", "Auto", "Disable", "")
        running = RunningConfigInterface(name="1/0/1", port_type="two-gigabitEthernet")

        self.assertEqual(
            diff_interface(desired, config, running),
            {
                "name": "1/0/1",
                "port_type": "two-gigabitEthernet",
                "enabled": False,
                "speed": "1000",
                "description": "Server Port",
                "pvid": 20,
                "vlans_untagged": [20],
                "vlans_tagged": [30],
                "vlans_disabled": [40],
                "acceptable_frame_type": "tagged",
            },
        )

    def test_omitted_settings_are_not_managed(self):
        # Everything omitted (defaults only) -> nothing to change.
        desired = _desired()
        config = InterfaceConfig("Tw1/0/1", "Enable", "10G", "Auto", "Disable", "Uplink")
        running = RunningConfigInterface(
            name="1/0/1",
            port_type="two-gigabitEthernet",
            description="Uplink",
            pvid=10,
            vlans_untagged=[10],
            acceptable_frame_type="tagged",
        )
        self.assertIsNone(diff_interface(desired, config, running))

    def test_speed_normalisation(self):
        # Module token '10000' == switch display '10G'.
        desired = _desired({"speed": "10000"})
        config = InterfaceConfig("Te1/0/25", "Enable", "10G", "Full", "Disable", "")
        running = RunningConfigInterface(name="1/0/25", port_type="ten-gigabitEthernet")
        self.assertIsNone(diff_interface(desired, config, running))

        # '1000' vs 'Auto' differs.
        desired = _desired({"speed": "1000"})
        config = InterfaceConfig("Tw1/0/1", "Enable", "Auto", "Auto", "Disable", "")
        self.assertEqual(
            diff_interface(desired, config, running)["speed"], "1000"
        )

    def test_empty_description_clears(self):
        desired = _desired({"description": ""})
        config = InterfaceConfig("Tw1/0/1", "Enable", "Auto", "Auto", "Disable", "Old")
        running = RunningConfigInterface(name="1/0/1", port_type="two-gigabitEthernet", description="Old")
        delta = diff_interface(desired, config, running)
        self.assertIsNone(delta["description"])  # None -> 'no description'

    def test_default_pvid_is_unchanged_when_omitted_from_running_config(self):
        running = parse_running_config("interface two-gigabitEthernet 1/0/1\n")[0]
        self.assertIsNone(diff_interface(_desired({"pvid": 1}), running=running))
        self.assertEqual(diff_interface(_desired({"pvid": 10}), running=running)["pvid"], 10)


class TestConfigureInterface(unittest.TestCase):
    def test_switch_errors_stop_configuration(self):
        for error in ("Error: Bad command", "% Invalid input", "Incomplete command"):
            with self.subTest(error=error):
                collector = ResultCollector()
                collector.set_basic_info(switch="192.0.2.10")
                config = InterfaceConfig("Tw1/0/1", "Enable", "Auto", "Auto", "Disable")
                running = RunningConfigInterface(name="1/0/1", port_type="two-gigabitEthernet")
                conn = MagicMock()
                with patch("plugins.modules.jetstream_interfaces_v2.ensure_global_config"), \
                     patch("plugins.modules.jetstream_interfaces_v2.require_config_mode"), \
                     patch("plugins.modules.jetstream_interfaces_v2.send_command",
                           side_effect=["", error]) as send:
                    with self.assertRaisesRegex(RuntimeError, "1/0/1.*speed 1000") as raised:
                        configure_interface(conn, _desired({"speed": "1000"}), config,
                                            running, collector, check_mode=False)
                self.assertIn(error, str(raised.exception))
                self.assertEqual(send.call_count, 2)
                conn.send_command_timing.assert_not_called()
                self.assertFalse(collector.changed)

    def test_error_on_exit_is_reported(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10")
        config = InterfaceConfig("Tw1/0/1", "Enable", "Auto", "Auto", "Disable")
        conn = MagicMock()
        conn.send_command_timing.return_value = "Error: Bad command"
        with patch("plugins.modules.jetstream_interfaces_v2.ensure_global_config"), \
             patch("plugins.modules.jetstream_interfaces_v2.require_config_mode"), \
             patch("plugins.modules.jetstream_interfaces_v2.send_command", return_value=""):
            with self.assertRaisesRegex(RuntimeError, "exit.*Error: Bad command"):
                configure_interface(conn, _desired({"speed": "1000"}), config,
                                    None, collector, check_mode=False)

    def test_check_mode_match_is_unchanged(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=True)

        desired = _desired({"enabled": True})
        config = InterfaceConfig("Tw1/0/1", "Enable", "Auto", "Auto", "Disable", "")
        running = RunningConfigInterface(name="1/0/1", port_type="two-gigabitEthernet")

        configure_interface(None, desired, config, running, collector, check_mode=True)

        self.assertFalse(collector.changed)
        step = collector._steps[-1]
        self.assertFalse(step["changed"])
        self.assertEqual(step["commands"], [])

    def test_check_mode_minimal_drift(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=True)

        desired = _desired({"description": "New Desc"})
        config = InterfaceConfig("Tw1/0/1", "Enable", "Auto", "Auto", "Disable", "Old Desc")
        running = RunningConfigInterface(name="1/0/1", port_type="two-gigabitEthernet", description="Old Desc")

        configure_interface(None, desired, config, running, collector, check_mode=True)

        self.assertTrue(collector.changed)
        step = collector._steps[-1]
        self.assertTrue(step["changed"])
        self.assertEqual(
            step["commands"],
            [
                "interface two-gigabitEthernet 1/0/1",
                'description "New Desc"',
                "exit",
            ],
        )

    def test_check_mode_full_drift(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=True)

        desired = _desired({
            "name": "1/0/2",
            "speed": "1000",
            "enabled": False,
            "description": "Server Port",
            "pvid": 20,
            "vlans_untagged": [20],
            "vlans_tagged": [30],
            "vlans_disabled": [40],
            "acceptable_frame_type": "tagged",
        })
        config = InterfaceConfig("Tw1/0/2", "Enable", "Auto", "Auto", "Disable", "")
        running = RunningConfigInterface(name="1/0/2", port_type="two-gigabitEthernet")

        configure_interface(None, desired, config, running, collector, check_mode=True)

        step = collector._steps[-1]
        self.assertTrue(step["changed"])
        self.assertEqual(
            step["commands"],
            [
                "interface two-gigabitEthernet 1/0/2",
                "shutdown",
                "speed 1000",
                "switchport pvid 20",
                "switchport general allowed vlan 20 untagged",
                "switchport general allowed vlan 30 tagged",
                "no switchport general allowed vlan 40",
                "switchport general acceptable-frame-type tagged-only",
                'description "Server Port"',
                "exit",
            ],
        )

    def test_acceptable_frame_type_all_reset(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=True)

        desired = _desired({"acceptable_frame_type": "all"})
        config = InterfaceConfig("Tw1/0/1", "Enable", "Auto", "Auto", "Disable", "")
        running = RunningConfigInterface(name="1/0/1", port_type="two-gigabitEthernet", acceptable_frame_type="tagged")

        configure_interface(None, desired, config, running, collector, check_mode=True)

        step = collector._steps[-1]
        self.assertTrue(step["changed"])
        self.assertEqual(
            step["commands"],
            [
                "interface two-gigabitEthernet 1/0/1",
                "switchport general acceptable-frame-type all",
                "exit",
            ],
        )


class TestRunModule(unittest.TestCase):
    def test_missing_port_fails_before_any_configuration_in_both_modes(self):
        for check_mode in (False, True):
            with self.subTest(check_mode=check_mode):
                module = MagicMock()
                module.params = {"host": "192.0.2.10", "interfaces": [
                    _desired({"name": "1/0/1"}),
                    _desired({"name": "1/0/999", "acceptable_frame_type": "all"}),
                ]}
                module.check_mode = check_mode
                module._verbosity = 0
                config = InterfaceConfig("Tw1/0/1", "Enable", "Auto", "Auto", "Disable")
                with patch("plugins.modules.jetstream_interfaces_v2.build_device", return_value={}), \
                     patch("plugins.modules.jetstream_interfaces_v2.ConnectHandler"), \
                     patch("plugins.modules.jetstream_interfaces_v2.get_interface_configuration",
                           return_value=[config]), \
                     patch("plugins.modules.jetstream_interfaces_v2.get_running_config", return_value=[]), \
                     patch("plugins.modules.jetstream_interfaces_v2.configure_interface") as configure:
                    with self.assertRaisesRegex(RuntimeError, "1/0/999"):
                        run_module(module)
                configure.assert_not_called()
                module.exit_json.assert_not_called()


if __name__ == "__main__":
    unittest.main()
