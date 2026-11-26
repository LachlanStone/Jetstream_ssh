"""Unit tests for interface_classes.InterfaceConfig and interface_parsers.parse_interface_configuration."""

import unittest

from plugins.module_utils.interfaces.interface_classes import InterfaceConfig
from plugins.module_utils.interfaces.interface_parsers import parse_interface_configuration


# ---------------------------------------------------------------------------
# Sample output — mirrors the real SG3428X-M2 output exactly
# ---------------------------------------------------------------------------
SAMPLE_OUTPUT = """\
SG3428X-M2#show interface configuration
 Port      State       Speed     Duplex    FlowCtrl    Description
 ----      -----       -----     ------    --------    -----------
 Tw1/0/1   Enable      Auto      Auto      Disable
 Tw1/0/2   Enable      Auto      Auto      Disable
 Tw1/0/3   Enable      Auto      Auto      Disable
 Tw1/0/4   Enable      Auto      Auto      Disable
 Tw1/0/5   Enable      Auto      Auto      Disable
 Tw1/0/6   Enable      Auto      Auto      Disable
 Tw1/0/7   Enable      Auto      Auto      Disable
 Tw1/0/8   Enable      Auto      Auto      Disable
 Tw1/0/9   Enable      Auto      Auto      Disable
 Tw1/0/10  Enable      Auto      Auto      Disable
 Tw1/0/11  Enable      Auto      Auto      Disable
 Tw1/0/12  Enable      Auto      Auto      Disable
 Tw1/0/13  Enable      Auto      Auto      Disable
 Tw1/0/14  Enable      Auto      Auto      Disable
 Tw1/0/15  Enable      Auto      Auto      Disable
 Tw1/0/16  Enable      Auto      Auto      Disable
 Tw1/0/17  Enable      Auto      Auto      Disable
 Tw1/0/18  Enable      Auto      Auto      Disable
 Tw1/0/19  Enable      Auto      Auto      Disable
 Tw1/0/20  Enable      Auto      Auto      Disable
 Tw1/0/21  Enable      Auto      Auto      Disable
 Tw1/0/22  Enable      Auto      Auto      Disable
 Tw1/0/23  Enable      Auto      Auto      Disable
 Tw1/0/24  Enable      Auto      Auto      Disable
 Te1/0/25  Enable      10G       Full      Disable
 Te1/0/26  Enable      10G       Full      Disable
 Te1/0/27  Enable      10G       Full      Disable
 Te1/0/28  Enable      10G       Full      Disable
"""

# Output with an inline description on one uplink port
SAMPLE_OUTPUT_WITH_DESCRIPTION = """\
SG3428X-M2#show interface configuration
 Port      State       Speed     Duplex    FlowCtrl    Description
 ----      -----       -----     ------    --------    -----------
 Tw1/0/1   Enable      Auto      Auto      Disable
 Tw1/0/2   Disable     Auto      Auto      Disable     Unused port
 Te1/0/25  Enable      10G       Full      Disable     Core uplink
"""

SAMPLE_OUTPUT_MIXED_FLOW = """\
SG3428X-M2#show interface configuration
 Port      State       Speed     Duplex    FlowCtrl    Description
 ----      -----       -----     ------    --------    -----------
 Tw1/0/1   Enable      Auto      Auto      Enable
 Te1/0/25  Disable     10G       Full      Disable
"""


# ---------------------------------------------------------------------------
# InterfaceConfig direct construction
# ---------------------------------------------------------------------------

class TestInterfaceConfigInit(unittest.TestCase):
    def test_basic_attributes(self):
        iface = InterfaceConfig(
            port="Tw1/0/1",
            state="Enable",
            speed="Auto",
            duplex="Auto",
            flow_ctrl="Disable",
        )
        self.assertEqual(iface.port, "Tw1/0/1")
        self.assertEqual(iface.state, "Enable")
        self.assertEqual(iface.speed, "Auto")
        self.assertEqual(iface.duplex, "Auto")
        self.assertEqual(iface.flow_ctrl, "Disable")
        self.assertEqual(iface.description, "")

    def test_enabled_flag_enable(self):
        iface = InterfaceConfig("Tw1/0/1", "Enable", "Auto", "Auto", "Disable")
        self.assertTrue(iface.enabled)

    def test_enabled_flag_disable(self):
        iface = InterfaceConfig("Tw1/0/2", "Disable", "Auto", "Auto", "Disable")
        self.assertFalse(iface.enabled)

    def test_enabled_flag_case_insensitive(self):
        iface = InterfaceConfig("Tw1/0/3", "ENABLE", "Auto", "Auto", "Disable")
        self.assertTrue(iface.enabled)

    def test_description_stored(self):
        iface = InterfaceConfig("Te1/0/25", "Enable", "10G", "Full", "Disable", "Core uplink")
        self.assertEqual(iface.description, "Core uplink")


# ---------------------------------------------------------------------------
# InterfaceConfig.from_parsed_line
# ---------------------------------------------------------------------------

class TestFromParsedLine(unittest.TestCase):
    def test_five_field_row(self):
        fields = ["Tw1/0/1", "Enable", "Auto", "Auto", "Disable"]
        iface = InterfaceConfig.from_parsed_line(fields)
        self.assertEqual(iface.port, "Tw1/0/1")
        self.assertEqual(iface.state, "Enable")
        self.assertEqual(iface.speed, "Auto")
        self.assertEqual(iface.duplex, "Auto")
        self.assertEqual(iface.flow_ctrl, "Disable")
        self.assertEqual(iface.description, "")
        self.assertTrue(iface.enabled)

    def test_six_field_row_single_word_description(self):
        fields = ["Te1/0/25", "Enable", "10G", "Full", "Disable", "Uplink"]
        iface = InterfaceConfig.from_parsed_line(fields)
        self.assertEqual(iface.description, "Uplink")

    def test_multi_word_description_joined(self):
        fields = ["Te1/0/26", "Enable", "10G", "Full", "Disable", "Core", "uplink", "switch"]
        iface = InterfaceConfig.from_parsed_line(fields)
        self.assertEqual(iface.description, "Core uplink switch")

    def test_too_few_fields_raises(self):
        with self.assertRaises(ValueError):
            InterfaceConfig.from_parsed_line(["Tw1/0/1", "Enable", "Auto", "Auto"])

    def test_disabled_port(self):
        fields = ["Tw1/0/2", "Disable", "Auto", "Auto", "Disable"]
        iface = InterfaceConfig.from_parsed_line(fields)
        self.assertFalse(iface.enabled)


# ---------------------------------------------------------------------------
# InterfaceConfig.from_dict
# ---------------------------------------------------------------------------

class TestFromDict(unittest.TestCase):
    def test_full_dict(self):
        data = {
            "port": "Te1/0/25",
            "state": "Enable",
            "speed": "10G",
            "duplex": "Full",
            "flow_ctrl": "Disable",
            "description": "Uplink",
        }
        iface = InterfaceConfig.from_dict(data)
        self.assertEqual(iface.port, "Te1/0/25")
        self.assertEqual(iface.speed, "10G")
        self.assertEqual(iface.duplex, "Full")
        self.assertEqual(iface.description, "Uplink")
        self.assertTrue(iface.enabled)

    def test_defaults_applied(self):
        iface = InterfaceConfig.from_dict({"port": "Tw1/0/1"})
        self.assertEqual(iface.state, "Enable")
        self.assertEqual(iface.speed, "Auto")
        self.assertEqual(iface.duplex, "Auto")
        self.assertEqual(iface.flow_ctrl, "Disable")
        self.assertEqual(iface.description, "")
        self.assertTrue(iface.enabled)

    def test_disabled_state(self):
        iface = InterfaceConfig.from_dict({"port": "Tw1/0/5", "state": "Disable"})
        self.assertFalse(iface.enabled)


# ---------------------------------------------------------------------------
# InterfaceConfig.to_dict
# ---------------------------------------------------------------------------

class TestToDict(unittest.TestCase):
    def test_round_trip(self):
        original = InterfaceConfig("Tw1/0/1", "Enable", "Auto", "Auto", "Disable", "My port")
        d = original.to_dict()
        self.assertEqual(d["port"], "Tw1/0/1")
        self.assertEqual(d["state"], "Enable")
        self.assertEqual(d["speed"], "Auto")
        self.assertEqual(d["duplex"], "Auto")
        self.assertEqual(d["flow_ctrl"], "Disable")
        self.assertEqual(d["description"], "My port")
        self.assertTrue(d["enabled"])

    def test_enabled_key_present(self):
        iface = InterfaceConfig("Tw1/0/2", "Disable", "Auto", "Auto", "Disable")
        d = iface.to_dict()
        self.assertIn("enabled", d)
        self.assertFalse(d["enabled"])


# ---------------------------------------------------------------------------
# parse_interface_configuration
# ---------------------------------------------------------------------------

class TestParseInterfaceConfiguration(unittest.TestCase):
    def setUp(self):
        self.interfaces = parse_interface_configuration(SAMPLE_OUTPUT)

    def test_port_count(self):
        self.assertEqual(len(self.interfaces), 28)

    def test_all_instances_are_interface_config(self):
        # Use the class name rather than assertIsInstance to avoid a false
        # negative when conftest.py's namespace-alias causes the parser to
        # return objects whose __class__ lives in a different module object.
        for iface in self.interfaces:
            self.assertEqual(type(iface).__name__, "InterfaceConfig")

    def test_first_port(self):
        iface = self.interfaces[0]
        self.assertEqual(iface.port, "Tw1/0/1")
        self.assertEqual(iface.state, "Enable")
        self.assertEqual(iface.speed, "Auto")
        self.assertEqual(iface.duplex, "Auto")
        self.assertEqual(iface.flow_ctrl, "Disable")
        self.assertEqual(iface.description, "")
        self.assertTrue(iface.enabled)

    def test_last_port(self):
        iface = self.interfaces[-1]
        self.assertEqual(iface.port, "Te1/0/28")
        self.assertEqual(iface.speed, "10G")
        self.assertEqual(iface.duplex, "Full")

    def test_sfp_ports_have_10g_full(self):
        sfp_ports = [i for i in self.interfaces if i.port.startswith("Te")]
        self.assertEqual(len(sfp_ports), 4)
        for iface in sfp_ports:
            self.assertEqual(iface.speed, "10G")
            self.assertEqual(iface.duplex, "Full")

    def test_copper_ports_have_auto(self):
        copper = [i for i in self.interfaces if i.port.startswith("Tw")]
        self.assertEqual(len(copper), 24)
        for iface in copper:
            self.assertEqual(iface.speed, "Auto")
            self.assertEqual(iface.duplex, "Auto")

    def test_port_name_list(self):
        names = [i.port for i in self.interfaces]
        self.assertIn("Tw1/0/1", names)
        self.assertIn("Te1/0/25", names)
        self.assertIn("Te1/0/28", names)
        self.assertEqual(names[0], "Tw1/0/1")

    def test_header_and_separator_lines_skipped(self):
        # The header ("Port State ...") and dashes line must not appear as ports
        names = [i.port for i in self.interfaces]
        self.assertNotIn("Port", names)
        self.assertNotIn("----", names)

    def test_prompt_line_skipped(self):
        names = [i.port for i in self.interfaces]
        # Switch prompt contains # and no slash
        self.assertFalse(any("#" in n for n in names))

    def test_description_parsed(self):
        interfaces = parse_interface_configuration(SAMPLE_OUTPUT_WITH_DESCRIPTION)
        by_port = {i.port: i for i in interfaces}
        self.assertEqual(by_port["Tw1/0/1"].description, "")
        self.assertEqual(by_port["Tw1/0/2"].description, "Unused port")
        self.assertEqual(by_port["Te1/0/25"].description, "Core uplink")

    def test_disabled_state_parsed(self):
        interfaces = parse_interface_configuration(SAMPLE_OUTPUT_WITH_DESCRIPTION)
        by_port = {i.port: i for i in interfaces}
        self.assertFalse(by_port["Tw1/0/2"].enabled)
        self.assertTrue(by_port["Tw1/0/1"].enabled)

    def test_flow_ctrl_enable_parsed(self):
        interfaces = parse_interface_configuration(SAMPLE_OUTPUT_MIXED_FLOW)
        by_port = {i.port: i for i in interfaces}
        self.assertEqual(by_port["Tw1/0/1"].flow_ctrl, "Enable")
        self.assertEqual(by_port["Te1/0/25"].flow_ctrl, "Disable")

    def test_empty_output_returns_empty_list(self):
        result = parse_interface_configuration("")
        self.assertEqual(result, [])

    def test_only_header_returns_empty_list(self):
        output = " Port      State       Speed     Duplex    FlowCtrl    Description\n ----      -----       -----     ------    --------    -----------\n"
        result = parse_interface_configuration(output)
        self.assertEqual(result, [])

    def test_port_order_preserved(self):
        names = [i.port for i in self.interfaces]
        expected = [f"Tw1/0/{n}" for n in range(1, 25)] + [f"Te1/0/{n}" for n in range(25, 29)]
        self.assertEqual(names, expected)


if __name__ == "__main__":
    unittest.main()
