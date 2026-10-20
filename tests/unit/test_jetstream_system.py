import unittest

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
        collector.set_basic_info(switch="192.0.2.10", check_mode=True, verbosity=4)
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
        self.assertEqual(collector.return_info()["commands_sent"], [])

    def test_configure_dns_check_mode(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=True, verbosity=4)
        dns_params = {
            "primary": "192.0.2.53",
            "secondary": "198.51.100.53",
        }
        configure_dns(None, dns_params, collector, check_mode=True)

        step = collector._steps[-1]
        self.assertFalse(step["changed"])
        self.assertIn("ip dns-address primary 192.0.2.53 secondary 198.51.100.53", step["commands"])
        self.assertEqual(collector.return_info()["commands_sent"], [])

    def test_configure_ntp_check_mode(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=True, verbosity=4)
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
        self.assertEqual(collector.return_info()["commands_sent"], [])

    def test_configure_lldp_check_mode(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=True, verbosity=4)

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
        self.assertEqual(collector.return_info()["commands_sent"], [])

    def test_configure_ntp_fewer_than_two_servers_records_failed_step(self):
        collector = ResultCollector()
        ntp_params = {
            "type": "ntp",
            "ntp_utc": "+00:00",
            "ntp_servers": ["192.0.2.1"],
            "ntp_fetch_time": 60,
        }
        configure_ntp(None, ntp_params, collector, check_mode=True)
        self.assertTrue(collector.failed)
        step = collector._steps[-1]
        self.assertFalse(step["changed"])
        self.assertIn("at least 2 servers", step["msg"])

    def test_configure_ntp_missing_utc_records_failed_step(self):
        collector = ResultCollector()
        ntp_params = {
            "type": "ntp",
            "ntp_servers": ["192.0.2.1", "192.0.2.2"],
            "ntp_fetch_time": 60,
        }
        configure_ntp(None, ntp_params, collector, check_mode=True)
        self.assertTrue(collector.failed)
        step = collector._steps[-1]
        self.assertFalse(step["changed"])
        self.assertIn("ntp_utc", step["msg"])

    def test_configure_ntp_missing_fetch_time_records_failed_step(self):
        collector = ResultCollector()
        ntp_params = {
            "type": "ntp",
            "ntp_utc": "+00:00",
            "ntp_servers": ["192.0.2.1", "192.0.2.2"],
        }
        configure_ntp(None, ntp_params, collector, check_mode=True)
        self.assertTrue(collector.failed)
        step = collector._steps[-1]
        self.assertFalse(step["changed"])
        self.assertIn("ntp_fetch_time", step["msg"])

    def test_configure_dns_secondary_without_primary_records_failed_step(self):
        collector = ResultCollector()
        dns_params = {"secondary": "198.51.100.53"}
        configure_dns(None, dns_params, collector, check_mode=True)
        self.assertTrue(collector.failed)
        step = collector._steps[-1]
        self.assertFalse(step["changed"])
        self.assertIn("requires 'primary'", step["msg"])


if __name__ == "__main__":
    unittest.main()
