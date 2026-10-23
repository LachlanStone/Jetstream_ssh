import argparse
import json
import logging
import os
import sys

import _bootstrap  # noqa: F401  puts repo root on sys.path

from plugins.modules.jetstream_acls import run_modules as _ansible_run_modules


def build_parser():
    parser = argparse.ArgumentParser(description="Live test for jetstream_acls")
    parser.add_argument("--host", default=os.environ.get("JETSTREAM_HOST", "192.0.2.10"), help="Switch IP or hostname")
    parser.add_argument("--username", default=os.environ.get("JETSTREAM_USERNAME", "admin"), help="SSH username")
    parser.add_argument("--password", default=os.environ.get("JETSTREAM_PASSWORD", "password"), help="SSH password")
    parser.add_argument("--enable-password", default=os.environ.get("JETSTREAM_ENABLE_PASSWORD", "password"), help="Enable password")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging to the terminal")
    return parser


from fake_module import FakeModule

from netmiko import ConnectHandler

from plugins.module_utils.acls.acls_parsers import (
    get_bound_access_lists,
    get_current_acls,
)
from plugins.module_utils.device import build_device

ACL_ID = "1000"
ACL_NAME = "ACL3"
VLAN_ID = 10

EXPECTED_STEPS = [
    "unbind_acl",
    "remove_acl",
    "create_and_update_acl",
    "create_and_update_acl_rules",
    "bind_acls",
]


def run_module_with_params(params):
    """
    Run the Ansible module logic with a plain params dict.
    Returns the result dictionary.
    """
    fake_module = FakeModule(params)
    try:
        returned = _ansible_run_modules(fake_module)
        # run_modules returns the result dict directly; use it if exit_json
        # was not called (no SystemExit raised).
        if returned is not None:
            return returned
        return fake_module._last_exit or {}
    except SystemExit as exc:
        if exc.code in (None, 0):
            return fake_module._last_exit or {}
        raise
    return fake_module._last_exit or {}


def check_results(results):
    """Assert the module reported the expected ACL lifecycle."""
    steps = results.get("steps", [])
    assert [step["name"] for step in steps] == EXPECTED_STEPS, [
        step["name"] for step in steps
    ]
    assert results["changed"] is True, results["changed"]
    assert results["msg"] == f"ACL {ACL_ID} has been bound.", results["msg"]
    assert results["cmd"] == f"access-list bind {ACL_ID} interface vlan {VLAN_ID}", results["cmd"]

    rule_step = next(
        step for step in steps if step["name"] == "create_and_update_acl_rules"
    )
    assert rule_step["changed"] is True, rule_step["changed"]
    assert (
        f"access-list combined {ACL_ID} rule 10 permit logging enable vid {VLAN_ID}"
        in rule_step["command"]
    ), rule_step["command"]


def check_device_state(params):
    """Read the switch back and assert the ACL and binding actually exist."""
    with ConnectHandler(**build_device(FakeModule(params))) as net_connect:
        net_connect.enable()
        current_acls = get_current_acls(net_connect)
        bound_acls = get_bound_access_lists(net_connect)

    assert ACL_ID in current_acls, current_acls
    acl = current_acls[ACL_ID]
    assert acl["name"] == ACL_NAME, acl
    assert acl["type"] == "combined", acl
    rules = {rule["seq"]: rule for rule in acl["rules"]}
    assert set(rules) == {10, 20}, rules
    assert rules[10]["action"] == "permit", rules[10]
    assert rules[20]["action"] == "permit", rules[20]

    assert ACL_ID in bound_acls, bound_acls
    binding = bound_acls[ACL_ID]
    assert binding.get("Interface/VID") == str(VLAN_ID), binding


if __name__ == "__main__":
    # --- Your params dict ---
    args = build_parser().parse_args()

    if args.verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            stream=sys.stdout,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        netmiko_logger = logging.getLogger("netmiko")
        netmiko_logger.setLevel(logging.DEBUG)
        netmiko_logger.propagate = True

    params = {
        "host": args.host,
        "port": 22,
        "username": args.username,
        "password": args.password,
        "enable_password": args.enable_password,
        "command_level": "enable",
        "command": None,
        "commands": ["show system-info", "show users", "show vlan"],
        "state": "update",
        "acls": {
            "id": "1000",
            "name": "ACL3",
            "vid": "10",
            "rule_type": "combined",
            "direction": "ingress",
            "rules": [
                {
                    "seq": 10,
                    "action": "permit",
                    "logging": "enable",
                    "sip": "10.0.0.0",
                    "sip_mask": "255.255.0.0",
                    "dip": "10.0.0.0",
                    "dip_mask": "255.255.0.0",
                    "protocol": 6,
                    "dport": 9100
                },
                {
                    "seq": 20,
                    "action": "permit",
                    "logging": "enable"
                }
            ]
        }
    }

    # --- Run the module ---
    try:
        results = run_module_with_params(params)
        print(json.dumps(results, indent=2))
        check_results(results)
        check_device_state(params)
        print("ACL live test validation passed.")
    except (RuntimeError, AssertionError) as e:
        print(json.dumps({"failed": True, "msg": str(e)}, indent=2))
        sys.exit(1)
