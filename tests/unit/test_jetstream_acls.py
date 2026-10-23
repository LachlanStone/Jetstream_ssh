import unittest
import unittest.mock as mock

from plugins.module_utils.collector import ResultCollector
from plugins.module_utils.acls.acl_classes import ACL
from plugins.modules.jetstream_acls import unbind_acl, remove_acl, run_modules
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
        self.assertFalse(step["changed"])
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
        self.assertFalse(step["changed"])
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


if __name__ == "__main__":
    unittest.main()
