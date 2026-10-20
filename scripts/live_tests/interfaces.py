import argparse
import json
import logging
import os
import sys

# Make the collection root importable when this script is run directly.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from ansible_collections.lachlanstone.jetstream.plugins.modules.jetstream_interfaces import (
    run_module as _ansible_run_module,
)


def build_parser():
    parser = argparse.ArgumentParser(description="Live test for jetstream_interfaces")
    parser.add_argument("--host", default=os.environ.get("JETSTREAM_HOST", "192.0.2.10"), help="Switch IP or hostname")
    parser.add_argument("--username", default=os.environ.get("JETSTREAM_USERNAME", "admin"), help="SSH username")
    parser.add_argument("--password", default=os.environ.get("JETSTREAM_PASSWORD", "password"), help="SSH password")
    parser.add_argument("--enable-password", default=os.environ.get("JETSTREAM_ENABLE_PASSWORD", "password"), help="Enable password")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging to the terminal")
    parser.add_argument("--check", action="store_true", help="Run in check mode (report only, no changes sent)")
    return parser

# True: report commands only, nothing is sent. False: push config to the real switch.
CHECK_MODE = False

PORTS = ["1/0/9", "1/0/10", "1/0/11"]


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
    "interfaces": [
        {
            "name": port,
            "port_type": "two-gigabitEthernet",
            "vlans_tagged": [20],
            "vlans_disabled": [10],
        }
        for port in PORTS
    ],
}


def check_results(results):
    """Assert the result matches the expected per-interface behavior."""
    steps = results.get("steps", [])
    assert len(steps) == len(PORTS), f"expected {len(PORTS)} steps, got {len(steps)}"
    for port, step in zip(PORTS, steps):
        assert step["name"] == f"configure_interface:{port}", step["name"]
        cmds = step.get("commands") or []
        assert "switchport general allowed vlan 20 tagged" in cmds, cmds
        assert "no switchport general allowed vlan 10" in cmds, cmds
        assert step["changed"] is (not args.check), f"{port}: changed={step['changed']}"


try:
    results = run_module_with_params(params, args.check)
    print(json.dumps(results, indent=2))
    check_results(results)
except (RuntimeError, AssertionError) as e:
    print(json.dumps({"failed": True, "msg": str(e)}, indent=2))
    sys.exit(1)
