import unittest
import unittest.mock as mock

from plugins.module_utils.collector import ResultCollector
from plugins.module_utils.acls.acl_classes import ACL, ACLRule
from plugins.module_utils.acls.acls_parsers import get_current_acls
from plugins.modules.jetstream_acls import (
    _rules_already_configured,
    create_and_update_acl,
    create_and_update_acl_rules,
    remove_acl,
    run_modules,
    unbind_acl,
)
from fake_module import FakeModule


class TestJetstreamAcls(unittest.TestCase):
    def setUp(self):
        self.collector = ResultCollector()
        self.collector.set_basic_info(switch="192.0.2.10", check_mode=True)

    def test_acl_from_dict_without_rules(self):
        # Ansible fills an omitted list suboption with None.
        acl = ACL.from_dict({"id": "100", "rules": None}, {}, {})

        self.assertEqual(acl.id, "100")
        self.assertEqual(acl.rules, [])

    def test_unbind_acl_state_present(self):
        fake_module = FakeModule({"state": "present"})
        acl = ACL(id="100", name="TEST_ACL", vid=10, rule_type="ip", is_bound=True, is_present=True)

        unbind_acl(None, self.collector, fake_module, acl)

        step = self.collector._steps[-1]
        self.assertFalse(step["changed"])
        self.assertIn("no unbind action required", step["msg"])

    def test_unbind_acl_check_mode(self):
        fake_module = FakeModule({"state": "unbind"})
        fake_module.check_mode = True
        acl = ACL(id="100", name="TEST_ACL", vid=10, rule_type="ip", is_bound=True, is_present=True)

        try:
            unbind_acl(None, self.collector, fake_module, acl)
        except SystemExit:
            pass

        step = self.collector._steps[-1]
        self.assertTrue(step["changed"])
        self.assertIn("would be unbound", step["msg"])

    def test_remove_acl_check_mode(self):
        fake_module = FakeModule({"state": "absent"})
        fake_module.check_mode = True
        acl = ACL(id="100", name="TEST_ACL", vid=10, rule_type="ip", is_bound=False, is_present=True)
        current_acls = {"100": {"id": "100", "type": "ip", "rules": []}}

        try:
            remove_acl(None, self.collector, fake_module, acl, current_acls)
        except SystemExit:
            pass

        step = self.collector._steps[-1]
        self.assertTrue(step["changed"])
        self.assertIn("would be removed", step["msg"])

    def test_run_modules_mock(self):
        params = {
            "host": "192.0.2.10",
            "port": 22,
            "username": "admin",
            "password": "pwd",
            "enable_password": "pwd",
            "state": "present",
            "acls": {
                "id": "100",
                "name": "TEST_ACL",
                "type": "ip",
                "rules": [
                    {
                        "seq": 10,
                        "action": "permit",
                        "protocol_name": "tcp",
                        "sip": "192.168.1.0",
                        "sip_mask": "0.0.0.255",
                        "dip": "10.0.0.1",
                        "dip_mask": "0.0.0.0",
                        "dport": "80",
                    }
                ],
            },
        }
        fake_module = FakeModule(params)
        fake_module.check_mode = True

        fake_conn = mock.MagicMock()
        fake_conn.__enter__.return_value = fake_conn
        fake_conn.config_mode.return_value = ""

        with mock.patch("plugins.modules.jetstream_acls.ConnectHandler", return_value=fake_conn), \
             mock.patch("plugins.modules.jetstream_acls.get_bound_access_lists", return_value={}), \
             mock.patch("plugins.modules.jetstream_acls.get_current_acls", return_value={}):
            result = run_modules(fake_module)

        self.assertIsNotNone(result)
        self.assertIn("steps", result)
        fake_conn.config_mode.assert_not_called()

    def test_parse_rule_fields(self):
        output = (
            'IP access list 100 name: "TEST_ACL"\n'
            "rule 10 permit logging disable sip 192.168.1.0 sip-mask 0.0.0.255 "
            "dip 10.0.0.1 dip-mask 0.0.0.0 protocol 6 d-port 80 d-port-mask 0000\n"
        )
        with mock.patch(
            "plugins.module_utils.acls.acls_parsers.send_command", return_value=output
        ):
            parsed = get_current_acls(None)

        rule = parsed["100"]["rules"][0]
        self.assertEqual(rule["seq"], 10)
        self.assertEqual(rule["action"], "permit")
        self.assertEqual(rule["logging"], "disable")
        self.assertEqual(rule["sip"], "192.168.1.0")
        self.assertEqual(rule["sip_mask"], "0.0.0.255")
        self.assertEqual(rule["dip"], "10.0.0.1")
        self.assertEqual(rule["protocol"], 6)
        self.assertEqual(rule["dport"], "80")
        self.assertEqual(rule["dport_mask"], "0000")

    def _acl_with_rule(self):
        acl = ACL(
            id="100",
            name="TEST_ACL",
            vid=None,
            rule_type="ip",
            is_bound=False,
            is_present=True,
        )
        acl.rules = [
            ACLRule(
                seq=10,
                action="permit",
                logging=False,
                sip="192.168.1.0",
                sip_mask="0.0.0.255",
                dip="10.0.0.1",
                dip_mask="0.0.0.0",
                protocol=6,
                dport="80",
                dport_mask="0000",
            )
        ]
        return acl

    def _current_acls_with_rule(self):
        return {
            "100": {
                "id": "100",
                "type": "ip",
                "rules": [
                    {
                        "seq": 10,
                        "action": "permit",
                        "logging": "disable",
                        "sip": "192.168.1.0",
                        "sip_mask": "0.0.0.255",
                        "dip": "10.0.0.1",
                        "dip_mask": "0.0.0.0",
                        "protocol": 6,
                        "dport": "80",
                        "dport_mask": "0000",
                    }
                ],
            }
        }

    def test_rules_already_configured(self):
        self.assertTrue(
            _rules_already_configured(
                self._acl_with_rule(), self._current_acls_with_rule()
            )
        )

    def test_rules_already_configured_detects_field_drift(self):
        current = self._current_acls_with_rule()
        current["100"]["rules"][0]["sip"] = "192.168.2.0"
        self.assertFalse(_rules_already_configured(self._acl_with_rule(), current))

    def test_rules_noop_sends_nothing(self):
        fake_module = FakeModule({"state": "present"})
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=False)

        with mock.patch("plugins.modules.jetstream_acls.send_command") as send:
            create_and_update_acl_rules(
                None,
                collector,
                fake_module,
                self._acl_with_rule(),
                self._current_acls_with_rule(),
            )

        send.assert_not_called()
        step = collector._steps[-1]
        self.assertFalse(step["changed"])
        self.assertIn("already configured", step["msg"])

    def test_update_check_mode_simulates_removal(self):
        fake_module = FakeModule({"state": "update"}, check_mode=True)
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=True)

        acl = ACL(
            id="100",
            name="TEST_ACL",
            vid=None,
            rule_type="ip",
            is_bound=True,
            is_present=True,
        )
        current = self._current_acls_with_rule()

        with mock.patch("plugins.modules.jetstream_acls.send_command") as send:
            remaining = remove_acl(None, collector, fake_module, acl, current)
            self.assertNotIn("100", remaining)
            acl.is_bound = False
            create_and_update_acl(None, collector, fake_module, acl, remaining)

        send.assert_not_called()
        self.assertTrue(collector.changed)

    def _run_present_with_current(self, state, current, bound, check_mode):
        params = {
            "host": "192.0.2.10",
            "port": 22,
            "username": "admin",
            "password": "pwd",
            "enable_password": "pwd",
            "state": state,
            "acls": {
                "id": "100",
                "name": "TEST_ACL",
                "type": "ip",
                "rules": [
                    {
                        "seq": 10,
                        "action": "permit",
                        "protocol": 6,
                        "sip": "192.168.1.0",
                        "sip_mask": "0.0.0.255",
                    }
                ],
            },
        }
        fake_module = FakeModule(params, check_mode=check_mode)
        fake_conn = mock.MagicMock()
        fake_conn.__enter__.return_value = fake_conn

        with mock.patch(
            "plugins.modules.jetstream_acls.ConnectHandler", return_value=fake_conn
        ), mock.patch(
            "plugins.modules.jetstream_acls.get_bound_access_lists",
            return_value=bound,
        ), mock.patch(
            "plugins.modules.jetstream_acls.get_current_acls", return_value=current
        ), mock.patch(
            "plugins.modules.jetstream_acls.send_command"
        ) as send:
            result = run_modules(fake_module)

        return result, send, fake_conn

    def test_run_modules_present_noop_is_unchanged(self):
        current = self._current_acls_with_rule()
        result, send, _ = self._run_present_with_current(
            "present", current, {"100": {"ACL ID": "100"}}, check_mode=False
        )

        send.assert_not_called()
        self.assertFalse(result["changed"])

    def test_run_modules_update_check_mode_completes(self):
        current = self._current_acls_with_rule()
        result, send, fake_conn = self._run_present_with_current(
            "update", current, {"100": {"ACL ID": "100"}}, check_mode=True
        )

        send.assert_not_called()
        fake_conn.config_mode.assert_not_called()
        self.assertTrue(result["changed"])


if __name__ == "__main__":
    unittest.main()
