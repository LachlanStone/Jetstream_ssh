"""Unit tests for jetstream_interfaces_v2 idempotent diffing."""

import unittest

from plugins.module_utils.collector import ResultCollector
from plugins.module_utils.interfaces.interface_classes import (
    InterfaceConfig,
    RunningConfigInterface,
    _port_id,
    diff_interface,
)
from plugins.modules.jetstream_interfaces_v2 import configure_interface


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


class TestConfigureInterface(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
