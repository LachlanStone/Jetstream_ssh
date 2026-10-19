from unittest.mock import patch

import unittest
import sys
import os
import types

# Ensure repository root is in sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Make the ansible-collection-style imports used by the source modules resolve
# to the in-repo plugins/ directory.  ``ansible_collections/`` is not tracked by
# git (it only held empty directories), so register the whole package chain as
# namespace packages in ``sys.modules``; this works even in a fresh checkout
# where ``ansible_collections/`` does not exist on disk.
_COLLECTION = "ansible_collections.lachlanstone.jetstream.plugins"
_REAL_PLUGINS = os.path.join(REPO_ROOT, "plugins")
for _pkg in (
    "ansible_collections",
    "ansible_collections.lachlanstone",
    "ansible_collections.lachlanstone.jetstream",
    _COLLECTION,
):
    if _pkg not in sys.modules:
        _m = types.ModuleType(_pkg)
        _m.__path__ = []
        sys.modules[_pkg] = _m
sys.modules[_COLLECTION].__path__ = [_REAL_PLUGINS]

from plugins.module_utils.collector import ResultCollector
from plugins.modules.jetstream_user import parse_user_output, manage_users


class TestJetstreamUser(unittest.TestCase):
    def test_parse_user_output_key_value(self):
        sample = """
User Name: admin
Privilege: admin
Status: enable

User Name: auditor
Privilege: guest
Status: enable
"""
        parsed = parse_user_output(sample)
        self.assertIn("admin", parsed)
        self.assertEqual(parsed["admin"]["privilege"], "admin")
        self.assertIn("auditor", parsed)
        self.assertEqual(parsed["auditor"]["privilege"], "guest")

    def test_parse_user_output_table(self):
        sample = """
User Name        Privilege        Status
----------------------------------------
admin            admin            enable
operator_1       operator         enable
power1           power_user       enable
user1            user             enable
guest1           guest            enable
"""
        parsed = parse_user_output(sample)
        self.assertEqual(len(parsed), 5)
        self.assertEqual(parsed["admin"]["privilege"], "admin")
        self.assertEqual(parsed["operator_1"]["privilege"], "operator")
        self.assertEqual(parsed["power1"]["privilege"], "power_user")
        self.assertEqual(parsed["user1"]["privilege"], "user")
        self.assertEqual(parsed["guest1"]["privilege"], "guest")

    def test_manage_users_check_mode(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=True, verbosity=4)

        user_entries = [
            {
                "name": "netops",
                "privilege": "admin",
                "password_type": "secret",
                "encryption_type": 0,
                "password": "MySecretPassword123",
                "state": "present",
            },
            {
                "name": "old_user",
                "state": "absent",
            },
        ]

        with self.assertLogs("netmiko", level="INFO") as logged:
            changed = manage_users(
                net_connect=None,
                user_entries=user_entries,
                collector=collector,
                check_mode=True,
            )

        self.assertTrue(changed)
        steps = collector._steps
        self.assertEqual(len(steps), 2)  # create, remove
        self.assertTrue(steps[0]["changed"])
        self.assertIn("user name netops privilege admin secret 0 <redacted>", steps[0]["commands"])
        self.assertIn("no user name old_user", steps[1]["commands"])
        self.assertNotIn("MySecretPassword123", repr(collector.return_info()))
        self.assertNotIn("MySecretPassword123", "\n".join(logged.output))
        self.assertEqual(collector.return_info()["commands_sent"], [])

    def test_manage_users_check_mode_idempotent(self):
        """Check mode reports changed=False when user already matches switch state."""
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=True, verbosity=4)

        class FakeNetConnect:
            def find_prompt(self):
                return "Switch#"

            def send_command(self, cmd, **kwargs):
                if "show user" in cmd:
                    return "User Name: netops\nPrivilege: admin\nStatus: enable\n"
                return ""

        user_entries = [
            {
                "name": "netops",
                "privilege": "admin",
                "password": "MySecretPassword123",
                "update_password": "on_create",
                "state": "present",
            },
        ]
        changed = manage_users(FakeNetConnect(), user_entries, collector, check_mode=True)
        self.assertFalse(changed)
        self.assertEqual(len(collector._steps), 0)

    def test_manage_users_check_mode_reports_planned_change(self):
        """Check mode reports changed=True when user does not match switch state."""
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=True, verbosity=4)

        class FakeNetConnect:
            def find_prompt(self):
                return "Switch#"

            def send_command(self, cmd, **kwargs):
                if "show user" in cmd:
                    return "User Name: netops\nPrivilege: admin\nStatus: enable\n"
                return ""

        user_entries = [
            {
                "name": "netops",
                "privilege": "operator",
                "password": "MySecretPassword123",
                "state": "present",
            },
        ]
        changed = manage_users(FakeNetConnect(), user_entries, collector, check_mode=True)
        self.assertTrue(changed)
        self.assertEqual(len(collector._steps), 1)
        self.assertTrue(collector._steps[0]["changed"])
        self.assertEqual(collector.return_info()["commands_sent"], [])

    def test_manage_users_privilege_update_without_password(self):
        """Existing user privilege can be updated without password when update_password != always."""
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=False, verbosity=4)

        class FakeNetConnect:
            def find_prompt(self):
                return "Switch#"

            def send_command(self, cmd, **kwargs):
                if "show user" in cmd:
                    return "User Name: netops\nPrivilege: admin\nStatus: enable\n"
                return ""

        user_entries = [
            {
                "name": "netops",
                "privilege": "operator",
                "update_password": "on_create",
                "state": "present",
            },
        ]
        changed = manage_users(FakeNetConnect(), user_entries, collector, check_mode=False)
        self.assertTrue(changed)
        self.assertEqual(len(collector._steps), 1)
        self.assertIn("user name netops privilege operator", collector._steps[0]["commands"][0])

    def test_manage_users_update_without_password_always_raises(self):
        """Existing user with update_password=always and no password raises ValueError."""
        collector = ResultCollector()
        user_entries = [
            {
                "name": "netops",
                "privilege": "admin",
                "update_password": "always",
                "state": "present",
            },
        ]
        with self.assertRaises(ValueError):
            manage_users(None, user_entries, collector, check_mode=True)

    def test_manage_users_deletion_preview_check_mode(self):
        """Check mode plans removal without sending commands."""
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=True, verbosity=4)

        user_entries = [{"name": "old_user", "state": "absent"}]
        changed = manage_users(None, user_entries, collector, check_mode=True)
        self.assertTrue(changed)
        self.assertEqual(len(collector._steps), 1)
        self.assertTrue(collector._steps[0]["changed"])
        self.assertIn("no user name old_user", collector._steps[0]["commands"])
        self.assertEqual(collector.return_info()["commands_sent"], [])

    def test_manage_users_redacts_password_but_sends_original(self):
        password = "MySecretPassword123"
        command = f"user name netops privilege admin secret 0 {password}"
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=False, verbosity=4)
        net_connect = object()

        with patch("plugins.modules.jetstream_user.send_command", side_effect=["", "", ""]) as send, self.assertLogs(
            "netmiko", level="INFO"
        ) as logged:
            changed = manage_users(
                net_connect,
                [{"name": "netops", "password": password}],
                collector,
            )

        self.assertTrue(changed)
        self.assertEqual(send.call_args_list[-1].kwargs["cmd"], command)
        result = collector.return_info()
        self.assertNotIn(password, repr(result))
        self.assertIn("<redacted>", repr(result))
        self.assertNotIn(password, "\n".join(logged.output))

    def test_invalid_username_length(self):
        collector = ResultCollector()
        user_entries = [{"name": "this_username_is_way_too_long_for_switch", "password": "pass"}]
        with self.assertRaises(ValueError):
            manage_users(None, user_entries, collector, check_mode=True)
    def test_idempotency_on_create(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.10", check_mode=False)

        # Mock net_connect that returns existing users
        class FakeNetConnect:
            def find_prompt(self):
                return "Switch#"
            def send_command(self, cmd, **kwargs):
                if "show user" in cmd:
                    return "User Name: admin\nPrivilege: admin\nStatus: enable\n"
                return ""

        fake_conn = FakeNetConnect()
        user_entries = [
            {
                "name": "admin",
                "privilege": "admin",
                "password": "newpass",
                "update_password": "on_create",
                "state": "present",
            }
        ]
        changed = manage_users(fake_conn, user_entries, collector, check_mode=False)
        self.assertFalse(changed)
        self.assertEqual(len(collector._steps), 0)

    def test_password_required_on_create(self):
        collector = ResultCollector()
        user_entries = [{"name": "newuser", "privilege": "admin", "state": "present", "password": None}]
        with self.assertRaises(ValueError):
            manage_users(None, user_entries, collector, check_mode=True)

    def test_invalid_username_spaces(self):
        collector = ResultCollector()
        user_entries = [{"name": "bad user", "password": "pass"}]
        with self.assertRaises(ValueError):
            manage_users(None, user_entries, collector, check_mode=True)


if __name__ == "__main__":
    unittest.main()
