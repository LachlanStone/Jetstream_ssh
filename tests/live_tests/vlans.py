import argparse
import json
import logging
import os
import sys

import _bootstrap  # noqa: F401  puts repo root on sys.path

from plugins.modules.jetstream_vlans import (
    run_module as _ansible_run_module,
)


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Live test for jetstream_vlans. Creates four test VLANs: a named "
            "VLAN with a static SVI, a named VLAN without an SVI, a DHCP SVI, "
            "and a bare VLAN."
        )
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("JETSTREAM_HOST", "192.0.2.10"),
        help="Switch IP or hostname",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("JETSTREAM_PORT", "22")),
        help="SSH port",
    )
    parser.add_argument(
        "--username",
        default=os.environ.get("JETSTREAM_USERNAME", "admin"),
        help="SSH username",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("JETSTREAM_PASSWORD", "password"),
        help="SSH password",
    )
    parser.add_argument(
        "--enable-password",
        default=os.environ.get("JETSTREAM_ENABLE_PASSWORD", "password"),
        help="Enable password",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging to the terminal",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run in check mode (report only, no changes sent)",
    )
    return parser


# True: report commands only, nothing is sent. False: push config to the real switch.
CHECK_MODE = False

VLANS = [
    {
        "vlan_id": 4000,
        "name": "LiveTest-Static",
        "ip_address": "192.0.2.10",
        "subnet_mask": "255.255.255.0",
        "ip_dhcp": False,
    },
    {
        "vlan_id": 4020,
        "name": "LiveTest-Clients",
        "ip_address": None,
        "subnet_mask": None,
        "ip_dhcp": False,
    },
    {
        "vlan_id": 4030,
        "name": None,
        "ip_address": None,
        "subnet_mask": None,
        "ip_dhcp": True,
    },
    {
        "vlan_id": 4040,
        "name": None,
        "ip_address": None,
        "subnet_mask": None,
        "ip_dhcp": False,
    },
]

EXPECTED_COMMANDS = [
    [
        "vlan 4000",
        "name LiveTest-Static",
        "exit",
        "interface vlan 4000",
        "ip address 192.0.2.10 255.255.255.0",
        "exit",
    ],
    ["vlan 4020", "name LiveTest-Clients", "exit"],
    ["vlan 4030", "exit", "interface vlan 4030", "ip address-alloc dhcp", "exit"],
    ["vlan 4040", "exit"],
]


from fake_module import FakeModule


def run_module_with_params(params, check_mode=False):
    """Run the Ansible module logic with a plain params dict. Returns the result dict."""
    fake_module = FakeModule(params, check_mode)
    try:
        _ansible_run_module(fake_module)
    except SystemExit as exc:
        if exc.code in (None, 0):
            return fake_module._last_exit or {}
        raise
    return fake_module._last_exit or {}


def check_results(results, check_mode):
    """Assert the result matches the expected per-VLAN behavior."""
    steps = results.get("steps", [])
    assert len(steps) == len(VLANS), f"expected {len(VLANS)} steps, got {len(steps)}"
    for vlan, expected, step in zip(VLANS, EXPECTED_COMMANDS, steps):
        vlan_id = vlan["vlan_id"]
        assert step["name"] == f"configure_vlan:{vlan_id}", step["name"]
        assert step["commands"] == expected, step["commands"]
        assert step["changed"] is (not check_mode), f"{vlan_id}: changed={step['changed']}"
        assert results["changed"] is (not check_mode), f"changed={results['changed']}"


if __name__ == "__main__":
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
        "port": args.port,
        "username": args.username,
        "password": args.password,
        "enable_password": args.enable_password,
        "vlans": VLANS,
    }

    check_mode = args.check or CHECK_MODE

    try:
        results = run_module_with_params(params, check_mode)
        print(json.dumps(results, indent=2))
        check_results(results, check_mode)
    except (RuntimeError, AssertionError) as e:
        print(json.dumps({"failed": True, "msg": str(e)}, indent=2))
        sys.exit(1)
