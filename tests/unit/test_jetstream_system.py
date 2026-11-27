import unittest
from unittest.mock import MagicMock, Mock, patch

from plugins.module_utils.collector import ResultCollector
from plugins.modules.jetstream_system import (
    set_general_information,
    configure_dns,
    configure_ntp,
    configure_lldp,
    normalize_utc_offset,
    parse_running_config,
    parse_system_info,
    read_system_info,
    run_module,
)


class TestJetstreamSystem(unittest.TestCase):
    def test_run_module_handles_omitted_system_block(self):
        module = Mock()
        module.params = {
            "host": "192.0.2.10",
            "port": 22,
            "username": "admin",
            "password": "",
            "enable_password": "",
            "read_timeout": 30,
            "system": None,
        }
        module.check_mode = True
        module._verbosity = 0

        with patch("plugins.modules.jetstream_system.ConnectHandler"):
            run_module(module)

        module.exit_json.assert_called_once()

    @staticmethod
    def _module_under_test(system, check_mode):
        module = Mock()
        module.params = {
            "host": "192.0.2.10",
            "port": 22,
            "username": "admin",
            "password": "",
            "enable_password": "",
            "read_timeout": 30,
            "system": system,
            "dns": None,
            "ntp": None,
            "lldp": None,
        }
        module.check_mode = check_mode
        module._verbosity = 4
        return module

    @staticmethod
    def _fake_connection():
        net_connect = MagicMock()
        net_connect.__enter__.return_value = net_connect
        return net_connect

    def test_run_module_check_mode_reports_no_change_when_matching(self):
        module = self._module_under_test({"hostname": "switch-01"}, check_mode=True)
        net_connect = self._fake_connection()

        with patch(
            "plugins.modules.jetstream_system.ConnectHandler", return_value=net_connect
        ), patch(
            "plugins.modules.jetstream_system.send_command",
            return_value="System Name - switch-01",
        ) as mock_send:
            run_module(module)

        module.exit_json.assert_called_once()
        result = module.exit_json.call_args.kwargs
        self.assertFalse(result["changed"])
        self.assertTrue(result["check_mode"])
        # Check mode reads the state but never enters config mode or sends config.
        net_connect.config_mode.assert_not_called()
        mock_send.assert_called_once_with(net_connect, cmd="show system-info")

    def test_run_module_check_mode_reports_change_without_sending(self):
        module = self._module_under_test({"hostname": "switch-02"}, check_mode=True)
        net_connect = self._fake_connection()

        with patch(
            "plugins.modules.jetstream_system.ConnectHandler", return_value=net_connect
        ), patch(
            "plugins.modules.jetstream_system.send_command",
            return_value="System Name - switch-01",
        ) as mock_send:
            run_module(module)

        module.exit_json.assert_called_once()
        result = module.exit_json.call_args.kwargs
        self.assertTrue(result["changed"])
        net_connect.config_mode.assert_not_called()
        # Only the read ran; the ``hostname switch-02`` command was not sent.
        mock_send.assert_called_once_with(net_connect, cmd="show system-info")

    def test_run_module_skips_config_when_state_already_matches(self):
        module = self._module_under_test({"hostname": "switch-01"}, check_mode=False)
        net_connect = self._fake_connection()

        with patch(
            "plugins.modules.jetstream_system.ConnectHandler", return_value=net_connect
        ), patch(
            "plugins.modules.jetstream_system.send_command",
            return_value="System Name - switch-01",
        ) as mock_send:
            run_module(module)

        module.exit_json.assert_called_once()
        result = module.exit_json.call_args.kwargs
        self.assertFalse(result["changed"])
        net_connect.config_mode.assert_called_once()
        mock_send.assert_called_once_with(net_connect, cmd="show system-info")

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

    def test_set_general_information_check_mode_already_matching(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=True, verbosity=4)
        system_params = {"hostname": "switch-01", "location": "Datacenter A"}
        current = {"hostname": "switch-01", "location": "Datacenter A"}

        set_general_information(
            None, system_params, collector, check_mode=True, current_system=current
        )

        self.assertFalse(collector.changed)
        step = collector._steps[-1]
        self.assertEqual(step["commands"], [])
        self.assertEqual(collector.return_info()["commands_sent"], [])

    def test_set_general_information_check_mode_reads_current_state(self):
        """Check mode must not over-report: it reads the switch first."""
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=True, verbosity=4)
        net_connect = MagicMock()
        output = (
            "System Description - TP-Link JetStream Switch\n"
            "System Name - switch-01\n"
            "System Location - Datacenter A\n"
            "Contact Information - ops@example.com\n"
        )

        with patch(
            "plugins.modules.jetstream_system.send_command", return_value=output
        ) as mock_send:
            set_general_information(
                net_connect,
                {"hostname": "switch-01", "location": "Datacenter A", "contact": "ops@example.com"},
                collector,
                check_mode=True,
            )

        mock_send.assert_called_once_with(net_connect, cmd="show system-info")
        self.assertFalse(collector.changed)
        self.assertEqual(collector._steps[-1]["commands"], [])

    def test_parse_system_info_dash_format(self):
        # Real ``show system-info`` output: ``Key - value`` lines, values may
        # contain colons (MAC address, system time).
        output = (
            "System Description - TP-Link JetStream Switch\n"
            "System Name - switch-01\n"
            "System Location - Server Room\n"
            "Contact Information - admin@example.com\n"
            "Mac Address - 00:11:22:33:44:55\n"
            "System Time - 2026-11-26 12:00:00\n"
        )
        self.assertEqual(
            parse_system_info(output),
            {
                "hostname": "switch-01",
                "location": "Server Room",
                "contact": "admin@example.com",
            },
        )

    def test_parse_system_info_colon_format(self):
        output = "Hostname: switch-01\nLocation: Server Room\nContact: ops@example.com\n"
        self.assertEqual(
            parse_system_info(output),
            {"hostname": "switch-01", "location": "Server Room", "contact": "ops@example.com"},
        )

    def test_read_system_info_without_connection(self):
        self.assertEqual(read_system_info(None), {})

    def test_parse_running_config(self):
        output = (
            "SG3428X-M2(config)#show running-config\n"
            "system-time ntp UTC pool.ntp.org 0.android.pool.ntp.org 12\n"
            "ip dns-address primary 192.0.2.53 secondary 198.51.100.53\n"
            "lldp\n"
            "end\n"
        )
        self.assertEqual(
            parse_running_config(output),
            {
                "ntp_utc": "UTC",
                "ntp_servers": ["pool.ntp.org", "0.android.pool.ntp.org"],
                "ntp_fetch_time": "12",
                "dns_primary": "192.0.2.53",
                "dns_secondary": "198.51.100.53",
                "lldp_enabled": True,
            },
        )

    def test_normalize_utc_offset(self):
        self.assertEqual(normalize_utc_offset("UTC"), "+00:00")
        self.assertEqual(normalize_utc_offset("GMT"), "+00:00")
        self.assertEqual(normalize_utc_offset("+00:00"), "+00:00")
        self.assertEqual(normalize_utc_offset("+10:00"), "+10:00")
        self.assertEqual(normalize_utc_offset("UTC+10:00"), "+10:00")
        self.assertEqual(normalize_utc_offset(None), "")

    def test_configure_dns_check_mode(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=True, verbosity=4)
        dns_params = {
            "primary": "192.0.2.53",
            "secondary": "198.51.100.53",
        }
        configure_dns(None, dns_params, collector, check_mode=True)

        step = collector._steps[-1]
        # State unknown (no switch to read) → check mode reports the change it would make.
        self.assertTrue(step["changed"])
        self.assertIn("ip dns-address primary 192.0.2.53 secondary 198.51.100.53", step["commands"])
        self.assertEqual(collector.return_info()["commands_sent"], [])

    def test_configure_dns_check_mode_already_matching(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=True, verbosity=4)
        dns_params = {"primary": "192.0.2.53", "secondary": "198.51.100.53"}
        current = {"dns_primary": "192.0.2.53", "dns_secondary": "198.51.100.53"}

        configure_dns(None, dns_params, collector, check_mode=True, current_config=current)

        step = collector._steps[-1]
        self.assertFalse(step["changed"])
        self.assertEqual(step["commands"], [])
        self.assertEqual(collector.return_info()["commands_sent"], [])

    def test_configure_dns_idempotent_when_already_configured(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=False, verbosity=4)
        dns_params = {"primary": "192.0.2.53"}
        current = {"dns_primary": "192.0.2.53", "dns_secondary": "198.51.100.53"}

        with patch("plugins.modules.jetstream_system.send_command") as mock_send:
            configure_dns(object(), dns_params, collector, check_mode=False, current_config=current)

        mock_send.assert_not_called()
        self.assertFalse(collector.changed)
        self.assertEqual(collector._steps[-1]["commands"], [])

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
        # State unknown (no switch to read) → check mode reports the change it would make.
        self.assertTrue(step["changed"])
        expected_cmd = "system-time ntp +00:00 192.0.2.123 198.51.100.123 60 203.0.113.123"
        self.assertIn(expected_cmd, step["commands"])
        self.assertEqual(collector.return_info()["commands_sent"], [])

    def test_configure_ntp_idempotent_when_running_config_matches(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=False, verbosity=4)
        ntp_params = {
            "type": "ntp",
            "ntp_utc": "+00:00",
            "ntp_servers": ["192.0.2.123", "198.51.100.123"],
            "ntp_fetch_time": 60,
        }
        # The switch prints its offset as ``UTC`` while the playbook uses ``+00:00``.
        current = {
            "ntp_utc": "UTC",
            "ntp_servers": ["192.0.2.123", "198.51.100.123"],
            "ntp_fetch_time": "60",
        }

        with patch("plugins.modules.jetstream_system.send_command") as mock_send:
            configure_ntp(object(), ntp_params, collector, check_mode=False, current_config=current)

        mock_send.assert_not_called()
        self.assertFalse(collector.changed)
        self.assertEqual(collector._steps[-1]["commands"], [])

    def test_configure_ntp_check_mode_reports_mismatch(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=True, verbosity=4)
        ntp_params = {
            "type": "ntp",
            "ntp_utc": "+00:00",
            "ntp_servers": ["192.0.2.123", "198.51.100.123"],
            "ntp_fetch_time": 60,
        }
        current = {
            "ntp_utc": "+00:00",
            "ntp_servers": ["192.0.2.123", "198.51.100.123"],
            "ntp_fetch_time": "30",
        }

        configure_ntp(None, ntp_params, collector, check_mode=True, current_config=current)

        step = collector._steps[-1]
        self.assertTrue(step["changed"])
        self.assertEqual(collector.return_info()["commands_sent"], [])

    def test_configure_lldp_check_mode(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=True, verbosity=4)

        # Test enable LLDP — state unknown, so the change is reported
        configure_lldp(None, {"enabled": True}, collector, check_mode=True)
        step = collector._steps[-1]
        self.assertTrue(step["changed"])
        self.assertIn("lldp run", step["commands"])

        # Test disable LLDP
        configure_lldp(None, {"enabled": False}, collector, check_mode=True)
        step2 = collector._steps[-1]
        self.assertTrue(step2["changed"])
        self.assertIn("no lldp run", step2["commands"])

        # Test omitted LLDP (should not emit commands)
        steps_before = len(collector._steps)
        configure_lldp(None, {}, collector, check_mode=True)
        self.assertEqual(len(collector._steps), steps_before)
        self.assertEqual(collector.return_info()["commands_sent"], [])

    def test_configure_lldp_idempotent_when_running_config_matches(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=False, verbosity=4)

        with patch("plugins.modules.jetstream_system.send_command") as mock_send:
            configure_lldp(
                object(),
                {"enabled": True},
                collector,
                check_mode=False,
                current_config={"lldp_enabled": True},
            )
            configure_lldp(
                object(),
                {"enabled": False},
                collector,
                check_mode=False,
                current_config={"lldp_enabled": False},
            )

        mock_send.assert_not_called()
        self.assertFalse(collector.changed)
        self.assertEqual(collector._steps[-1]["commands"], [])

    def test_configure_lldp_check_mode_reports_mismatch(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=True, verbosity=4)

        configure_lldp(
            None,
            {"enabled": False},
            collector,
            check_mode=True,
            current_config={"lldp_enabled": True},
        )

        step = collector._steps[-1]
        self.assertTrue(step["changed"])
        self.assertIn("no lldp run", step["commands"])
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
