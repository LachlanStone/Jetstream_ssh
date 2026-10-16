import unittest
import sys
import os
import types

# Ensure repository root is in sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Make the ansible-collection-style imports used by the source modules resolve
# to the in-repo plugins/ package (ansible_collections/... is empty in this checkout).
_COLLECTION = "ansible_collections.lachlanstone.jetstream.plugins"
if _COLLECTION not in sys.modules:
    _collection_pkg = types.ModuleType(_COLLECTION)
    _collection_pkg.__path__ = [os.path.join(REPO_ROOT, "plugins")]
    sys.modules[_COLLECTION] = _collection_pkg

from plugins.module_utils.collector import ResultCollector
from plugins.modules.jetstream_system import (
    set_general_information,
    configure_dns,
    configure_ntp,
    configure_lldp,
)


class TestJetstreamSystem(unittest.TestCase):
    def test_set_general_information_check_mode(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=True)
        system_params = {
            "hostname": "switch-01",
            "location": "Datacenter A",
            "contact": "ops@example.com",
        }
        set_general_information(None, system_params, collector, check_mode=True)

        self.assertTrue(collector.changed)
        step = collector._steps[-1]
        self.assertIn("hostname switch-01", step["commands"])
        self.assertIn("location Datacenter A", step["commands"])
        self.assertIn("contact-info ops@example.com", step["commands"])

    def test_configure_dns_check_mode(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=True)
        dns_params = {
            "primary": "192.0.2.53",
            "secondary": "198.51.100.53",
        }
        configure_dns(None, dns_params, collector, check_mode=True)

        step = collector._steps[-1]
        self.assertFalse(step["changed"])
        self.assertIn("ip dns-address primary 192.0.2.53 secondary 198.51.100.53", step["commands"])

    def test_configure_ntp_check_mode(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=True)
        ntp_params = {
            "type": "ntp",
            "ntp_utc": "+00:00",
            "ntp_servers": ["192.0.2.123", "198.51.100.123", "203.0.113.123"],
            "ntp_fetch_time": 60,
        }
        configure_ntp(None, ntp_params, collector, check_mode=True)

        step = collector._steps[-1]
        self.assertFalse(step["changed"])
        expected_cmd = "system-time ntp +00:00 192.0.2.123 198.51.100.123 60 203.0.113.123"
        self.assertIn(expected_cmd, step["commands"])

    def test_configure_lldp_check_mode(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=True)

        # Test enable LLDP
        configure_lldp(None, {"enabled": True}, collector, check_mode=True)
        step = collector._steps[-1]
        self.assertFalse(step["changed"])
        self.assertIn("lldp run", step["commands"])

        # Test disable LLDP
        configure_lldp(None, {"enabled": False}, collector, check_mode=True)
        step2 = collector._steps[-1]
        self.assertFalse(step2["changed"])
        self.assertIn("no lldp run", step2["commands"])

        # Test omitted LLDP (should not emit commands)
        steps_before = len(collector._steps)
        configure_lldp(None, {}, collector, check_mode=True)
        self.assertEqual(len(collector._steps), steps_before)

    def test_configure_ntp_fewer_than_two_servers_raises_error(self):
        collector = ResultCollector()
        ntp_params = {
            "type": "ntp",
            "ntp_utc": "+00:00",
            "ntp_servers": ["192.0.2.1"],
            "ntp_fetch_time": 60,
        }
        with self.assertRaises(ValueError) as ctx:
            configure_ntp(None, ntp_params, collector, check_mode=True)
        self.assertIn("at least 2 servers", str(ctx.exception))

    def test_configure_ntp_missing_utc_raises_error(self):
        collector = ResultCollector()
        ntp_params = {
            "type": "ntp",
            "ntp_servers": ["192.0.2.1", "192.0.2.2"],
            "ntp_fetch_time": 60,
        }
        with self.assertRaises(ValueError) as ctx:
            configure_ntp(None, ntp_params, collector, check_mode=True)
        self.assertIn("ntp_utc", str(ctx.exception))

    def test_configure_ntp_missing_fetch_time_raises_error(self):
        collector = ResultCollector()
        ntp_params = {
            "type": "ntp",
            "ntp_utc": "+00:00",
            "ntp_servers": ["192.0.2.1", "192.0.2.2"],
        }
        with self.assertRaises(ValueError) as ctx:
            configure_ntp(None, ntp_params, collector, check_mode=True)
        self.assertIn("ntp_fetch_time", str(ctx.exception))

    def test_configure_dns_secondary_without_primary_raises_error(self):
        collector = ResultCollector()
        dns_params = {"secondary": "198.51.100.53"}
        with self.assertRaises(ValueError) as ctx:
            configure_dns(None, dns_params, collector, check_mode=True)
        self.assertIn("requires 'primary'", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
