"""Unit tests for RunningConfigInterface and parse_running_config."""

import unittest

from plugins.module_utils.interfaces.interface_classes import RunningConfigInterface
from plugins.module_utils.interfaces.interface_parsers import parse_running_config


# ---------------------------------------------------------------------------
# Sample output — mirrors the real SG3428X-M2 ``show running-config`` exactly
# ---------------------------------------------------------------------------
SAMPLE_FULL = """\
SG3428X-M2(config-if)#show running-config
!SG3428X-M2
#
vlan 1
 name "System-VLAN"
#
vlan 10-11
#
serial_port baud_rate 38400
#
system-time ntp UTC pool.ntp.org 0.android.pool.ntp.org 12
no system-time dst
#
user name admin privilege admin secret 5 $1$E>D<L;C:E9J6F4M5A<H2B6M=K7H1L>I8}{][/
telnet disable
no service reset-disable
#
spanning-tree
spanning-tree mode rstp
#
no snmp-server
#
no ip http server
#
lldp
#
ip route 0.0.0.0 0.0.0.0 10.10.10.1
#
no controller cloud-based
#
interface vlan 1
  ip address-alloc dhcp
  ipv6 enable
#
interface vlan 10
  ip address 10.10.10.50 255.255.255.0
  no ipv6 enable
#
interface two-gigabitEthernet 1/0/1
  switchport general allowed vlan 11 untagged
  switchport general allowed vlan 10 tagged
  switchport acceptable frame tagged
  no switchport general allowed vlan 1
  spanning-tree

#
interface two-gigabitEthernet 1/0/2
  switchport general allowed vlan 10 tagged
  spanning-tree

#
interface two-gigabitEthernet 1/0/3
  spanning-tree

#
interface two-gigabitEthernet 1/0/4
  spanning-tree

#
interface two-gigabitEthernet 1/0/5
  spanning-tree

#
interface two-gigabitEthernet 1/0/6
  spanning-tree

#
interface two-gigabitEthernet 1/0/7
  spanning-tree

#
interface two-gigabitEthernet 1/0/8
  spanning-tree

#
interface two-gigabitEthernet 1/0/9
  spanning-tree

#
interface two-gigabitEthernet 1/0/10
  spanning-tree

#
interface two-gigabitEthernet 1/0/11
  spanning-tree

#
interface two-gigabitEthernet 1/0/12
  spanning-tree

#
interface two-gigabitEthernet 1/0/13
  spanning-tree

#
interface two-gigabitEthernet 1/0/14
  spanning-tree

#
interface two-gigabitEthernet 1/0/15
  spanning-tree

#
interface two-gigabitEthernet 1/0/16
  spanning-tree

#
interface two-gigabitEthernet 1/0/17
  spanning-tree

#
interface two-gigabitEthernet 1/0/18
  spanning-tree

#
interface two-gigabitEthernet 1/0/19
  spanning-tree

#
interface two-gigabitEthernet 1/0/20
  spanning-tree

#
interface two-gigabitEthernet 1/0/21
  spanning-tree

#
interface two-gigabitEthernet 1/0/22
  spanning-tree

#
interface two-gigabitEthernet 1/0/23
  spanning-tree

#
interface two-gigabitEthernet 1/0/24
  spanning-tree

#
interface ten-gigabitEthernet 1/0/25
  spanning-tree

#
interface ten-gigabitEthernet 1/0/26
  spanning-tree

#
interface ten-gigabitEthernet 1/0/27
  spanning-tree

#
interface ten-gigabitEthernet 1/0/28
  spanning-tree

#
end
"""

SAMPLE_SINGLE = """\
SG3428X-M2#show running-config interface two-gigabitEthernet 1/0/1
!SG3428X-M2
interface two-gigabitEthernet 1/0/1
  switchport general allowed vlan 11 untagged
  switchport general allowed vlan 10 tagged
  switchport acceptable frame tagged
  no switchport general allowed vlan 1
  spanning-tree

#
"""


# ---------------------------------------------------------------------------
# RunningConfigInterface construction and (de)serialisation
# ---------------------------------------------------------------------------

class TestRunningConfigInterface(unittest.TestCase):
    def test_defaults(self):
        iface = RunningConfigInterface(name="1/0/1", port_type="two-gigabitEthernet")
        self.assertEqual(iface.name, "1/0/1")
        self.assertEqual(iface.port_type, "two-gigabitEthernet")
        self.assertEqual(iface.description, "")
        self.assertIsNone(iface.pvid)
        self.assertEqual(iface.vlans_untagged, [])
        self.assertEqual(iface.vlans_tagged, [])
        self.assertEqual(iface.vlans_disabled, [])
        self.assertEqual(iface.acceptable_frame_type, "all")
        self.assertIsNone(iface.flowcontrol)

    def test_to_dict_round_trip(self):
        iface = RunningConfigInterface(
            name="1/0/1",
            port_type="two-gigabitEthernet",
            description="Uplink",
            pvid=11,
            vlans_untagged=[11],
            vlans_tagged=[10, 12],
            vlans_disabled=[1],
            acceptable_frame_type="tagged",
        )
        d = iface.to_dict()
        self.assertEqual(d["name"], "1/0/1")
        self.assertEqual(d["port_type"], "two-gigabitEthernet")
        self.assertEqual(d["description"], "Uplink")
        self.assertEqual(d["pvid"], 11)
        self.assertEqual(d["vlans_untagged"], [11])
        self.assertEqual(d["vlans_tagged"], [10, 12])
        self.assertEqual(d["vlans_disabled"], [1])
        self.assertEqual(d["acceptable_frame_type"], "tagged")
        self.assertIsNone(d["flowcontrol"])

    def test_from_dict(self):
        data = {
            "name": "1/0/1",
            "port_type": "two-gigabitEthernet",
            "description": "Uplink",
            "pvid": 11,
            "vlans_untagged": [11],
            "vlans_tagged": [10],
            "vlans_disabled": [1],
            "acceptable_frame_type": "tagged",
        }
        iface = RunningConfigInterface.from_dict(data)
        self.assertEqual(iface.name, "1/0/1")
        self.assertEqual(iface.pvid, 11)
        self.assertEqual(iface.vlans_tagged, [10])
        self.assertIsNone(iface.flowcontrol)


# ---------------------------------------------------------------------------
# parse_running_config — full config
# ---------------------------------------------------------------------------

class TestParseRunningConfigFull(unittest.TestCase):
    def setUp(self):
        self.interfaces = parse_running_config(SAMPLE_FULL)

    def test_all_instances_are_running_config_interface(self):
        for iface in self.interfaces:
            self.assertEqual(type(iface).__name__, "RunningConfigInterface")

    def test_physical_interface_count(self):
        # 24 two-gigabit + 4 ten-gigabit = 28 physical ports; vlan blocks skipped.
        self.assertEqual(len(self.interfaces), 28)

    def test_vlan_interfaces_skipped(self):
        names = [(i.port_type, i.name) for i in self.interfaces]
        self.assertNotIn(("vlan", "1"), names)
        self.assertNotIn(("vlan", "10"), names)

    def test_port_order_preserved(self):
        names = [i.name for i in self.interfaces]
        expected = [f"1/0/{n}" for n in range(1, 25)] + [f"1/0/{n}" for n in range(25, 29)]
        self.assertEqual(names, expected)

    def test_configured_port_1_0_1(self):
        iface = self.interfaces[0]
        self.assertEqual(iface.port_type, "two-gigabitEthernet")
        self.assertEqual(iface.name, "1/0/1")
        self.assertEqual(iface.vlans_untagged, [11])
        self.assertEqual(iface.vlans_tagged, [10])
        self.assertEqual(iface.vlans_disabled, [1])
        self.assertEqual(iface.acceptable_frame_type, "tagged")
        self.assertIsNone(iface.pvid)
        self.assertEqual(iface.description, "")

    def test_configured_port_1_0_2(self):
        iface = self.interfaces[1]
        self.assertEqual(iface.vlans_tagged, [10])
        self.assertEqual(iface.vlans_untagged, [])
        self.assertEqual(iface.acceptable_frame_type, "all")

    def test_bare_port_defaults(self):
        iface = self.interfaces[2]  # two-gigabitEthernet 1/0/3
        self.assertEqual(iface.name, "1/0/3")
        self.assertEqual(iface.vlans_untagged, [])
        self.assertEqual(iface.vlans_tagged, [])
        self.assertEqual(iface.vlans_disabled, [])
        self.assertEqual(iface.acceptable_frame_type, "all")
        self.assertIsNone(iface.pvid)
        self.assertEqual(iface.description, "")

    def test_ten_gigabit_port(self):
        iface = self.interfaces[-1]
        self.assertEqual(iface.port_type, "ten-gigabitEthernet")
        self.assertEqual(iface.name, "1/0/28")


# ---------------------------------------------------------------------------
# parse_running_config — single interface
# ---------------------------------------------------------------------------

class TestParseRunningConfigSingle(unittest.TestCase):
    def setUp(self):
        self.interfaces = parse_running_config(SAMPLE_SINGLE)

    def test_single_interface_count(self):
        self.assertEqual(len(self.interfaces), 1)

    def test_single_interface_fields(self):
        iface = self.interfaces[0]
        self.assertEqual(iface.port_type, "two-gigabitEthernet")
        self.assertEqual(iface.name, "1/0/1")
        self.assertEqual(iface.vlans_untagged, [11])
        self.assertEqual(iface.vlans_tagged, [10])
        self.assertEqual(iface.vlans_disabled, [1])
        self.assertEqual(iface.acceptable_frame_type, "tagged")
        self.assertIsNone(iface.pvid)


# ---------------------------------------------------------------------------
# parse_running_config — subcommand details
# ---------------------------------------------------------------------------

class TestParseRunningConfigDetails(unittest.TestCase):
    def _parse_one(self, body):
        output = f"interface two-gigabitEthernet 1/0/1\n{body}\n"
        result = parse_running_config(output)
        self.assertEqual(len(result), 1)
        return result[0]

    def test_pvid(self):
        iface = self._parse_one("  switchport pvid 11\n")
        self.assertEqual(iface.pvid, 11)

    def test_no_pvid(self):
        iface = self._parse_one("  switchport pvid 11\n  no switchport pvid\n")
        self.assertIsNone(iface.pvid)

    def test_vlan_range_tagged(self):
        iface = self._parse_one("  switchport general allowed vlan 10-12 tagged\n")
        self.assertEqual(iface.vlans_tagged, [10, 11, 12])

    def test_vlan_comma_list_untagged(self):
        iface = self._parse_one("  switchport general allowed vlan 10,11,12 untagged\n")
        self.assertEqual(iface.vlans_untagged, [10, 11, 12])

    def test_disabled_vlan_range(self):
        iface = self._parse_one("  no switchport general allowed vlan 2-4\n")
        self.assertEqual(iface.vlans_disabled, [2, 3, 4])

    def test_description_quoted(self):
        iface = self._parse_one('  description "Server uplink"\n')
        self.assertEqual(iface.description, "Server uplink")

    def test_description_unquoted(self):
        iface = self._parse_one("  description Printer\n")
        self.assertEqual(iface.description, "Printer")

    def test_no_description(self):
        iface = self._parse_one('  description "Server uplink"\n  no description\n')
        self.assertEqual(iface.description, "")

    def test_acceptable_frame_all_explicit(self):
        iface = self._parse_one("  switchport acceptable frame all\n")
        self.assertEqual(iface.acceptable_frame_type, "all")

    def test_empty_output(self):
        self.assertEqual(parse_running_config(""), [])


if __name__ == "__main__":
    unittest.main()
