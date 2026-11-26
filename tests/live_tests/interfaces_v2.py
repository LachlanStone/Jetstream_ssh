"""Live test for jetstream_interfaces_v2 (idempotent interface configuration).

Mirrors ``tests/live_tests/interfaces.py`` but exercises the v2 module, which
reads the current state first and only sends the commands for settings that
differ.

Usage::

    python tests/live_tests/interfaces_v2.py --host <switch> --username admin \
        --password <pw> --enable-password <pw>

The default run applies the config once, then runs it again to prove
idempotency: the second run must report ``changed=false`` and send no commands.
Pass ``--check`` to run a single check-mode pass instead (report only).
"""

import argparse
import json
import logging
import os
import sys

import _bootstrap  # noqa: F401  puts repo root on sys.path

from plugins.modules.jetstream_interfaces_v2 import (
    run_module as _ansible_run_module,
)
from fake_module import FakeModule


def build_parser():
    parser = argparse.ArgumentParser(description="Live test for jetstream_interfaces_v2")
    parser.add_argument("--host", default=os.environ.get("JETSTREAM_HOST", "192.0.2.10"), help="Switch IP or hostname")
    parser.add_argument("--username", default=os.environ.get("JETSTREAM_USERNAME", "admin"), help="SSH username")
    parser.add_argument("--password", default=os.environ.get("JETSTREAM_PASSWORD", "password"), help="SSH password")
    parser.add_argument("--enable-password", default=os.environ.get("JETSTREAM_ENABLE_PASSWORD", "password"), help="Enable password")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging to the terminal")
    parser.add_argument("--check", action="store_true", help="Run in check mode (report only; no idempotency check)")
    return parser


PORTS = ["1/0/9", "1/0/10", "1/0/11"]


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


def _assert_apply_commands(results):
    """Sanity-check that any applied step contains the expected VLAN commands."""
    steps = results.get("steps", [])
    assert len(steps) == len(PORTS), f"expected {len(PORTS)} steps, got {len(steps)}"
    for port, step in zip(PORTS, steps):
        assert step["name"] == f"configure_interface:{port}", step["name"]
        cmds = step.get("commands") or []
        if step.get("changed"):
            assert "switchport general allowed vlan 20 tagged" in cmds, cmds
            assert "no switchport general allowed vlan 10" in cmds, cmds


def _assert_idempotent(results):
    """Assert a second run reports no changes and sends no commands."""
    assert results.get("changed") is False, f"idempotency run changed={results.get('changed')}"
    steps = results.get("steps", [])
    assert len(steps) == len(PORTS), f"expected {len(PORTS)} steps, got {len(steps)}"
    for port, step in zip(PORTS, steps):
        assert step["changed"] is False, f"{port}: changed={step['changed']}"
        assert (step.get("commands") or []) == [], f"{port}: commands={step.get('commands')}"


try:
    if args.check:
        results = run_module_with_params(params, check_mode=True)
        print(json.dumps(results, indent=2))
        print("Check mode: diff reported above; nothing was sent, so idempotency is not checked.")
    else:
        first = run_module_with_params(params, check_mode=False)
        print("--- apply run ---")
        print(json.dumps(first, indent=2))
        _assert_apply_commands(first)

        second = run_module_with_params(params, check_mode=False)
        print("--- idempotency run ---")
        print(json.dumps(second, indent=2))
        _assert_idempotent(second)
        print("OK: second run made no changes (idempotent).")
except (RuntimeError, AssertionError) as e:
    print(json.dumps({"failed": True, "msg": str(e)}, indent=2))
    sys.exit(1)
