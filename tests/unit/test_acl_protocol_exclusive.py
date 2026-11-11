import unittest

from plugins.module_utils.acls.acl_classes import ACL
from plugins.modules.jetstream_acls import validate_acl_rules


class TestAclProtocolExclusive(unittest.TestCase):
    def _acl_with_rule(self, **rule):
        return ACL.from_dict(
            acl={
                "id": "100",
                "name": "TEST_ACL",
                "vid": 10,
                "rule_type": "combined",
                "rules": [{"seq": 10, "action": "permit", **rule}],
            },
            bound_acls=[],
            current_acls={},
        )

    def test_protocol_and_protocol_name_together_is_rejected(self):
        acl = self._acl_with_rule(protocol=6, protocol_name="TCP")

        with self.assertRaises(ValueError) as ctx:
            validate_acl_rules(acl)

        self.assertIn("mutually exclusive", str(ctx.exception))

    def test_protocol_only_is_allowed(self):
        acl = self._acl_with_rule(protocol=6)

        self.assertIsNone(validate_acl_rules(acl))

    def test_protocol_name_only_is_allowed(self):
        acl = self._acl_with_rule(protocol_name="TCP")

        self.assertIsNone(validate_acl_rules(acl))


if __name__ == "__main__":
    unittest.main()
