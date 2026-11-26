"""Live test — parse ``show interface configuration`` from a real switch.

Connects over SSH, runs the command, parses the output with
``parse_interface_configuration``, and asserts that the result makes sense for a
28-port SG3428X-M2 (24 × 2.5G copper + 4 × 10G SFP).

Usage::

    # Credentials from env (recommended)
    JETSTREAM_HOST=192.0.2.10 JETSTREAM_USERNAME=admin JETSTREAM_PASSWORD=secret \\
        python3 tests/live_tests/interface_config.py

    # Or pass on the command line
    python3 tests/live_tests/interface_config.py --host 192.0.2.10 --username admin --password secret
"""

import argparse
import json
import logging
import os
import sys

import _bootstrap  # noqa: F401  puts repo root on sys.path

from netmiko import ConnectHandler

from ansible_collections.lachlanstone.jetstream.plugins.module_utils.interfaces.interface_classes import (
    InterfaceConfig,
)
from plugins.module_utils.interfaces.interface_parsers import (
    get_interface_configuration,
    parse_interface_configuration,
)
from plugins.module_utils.device import build_device
from fake_module import FakeModule


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(description="Live test — show interface configuration parser")
    p.add_argument("--host",            default=os.environ.get("JETSTREAM_HOST", "192.0.2.10"))
    p.add_argument("--username",        default=os.environ.get("JETSTREAM_USERNAME", "admin"))
    p.add_argument("--password",        default=os.environ.get("JETSTREAM_PASSWORD", "password"))
    p.add_argument("--enable-password", default=os.environ.get("JETSTREAM_ENABLE_PASSWORD", "password"))
    p.add_argument("-v", "--verbose",   action="store_true")
    return p


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def check_interfaces(interfaces: list, *, expected_count: int = 28):
    """Assert the parsed interface list is well-formed for an SG3428X-M2."""
    assert len(interfaces) == expected_count, (
        f"Expected {expected_count} interfaces, got {len(interfaces)}"
    )

    for iface in interfaces:
        assert isinstance(iface, InterfaceConfig), f"Not an InterfaceConfig: {iface!r}"
        assert iface.port, f"Empty port name in {iface!r}"
        assert iface.state in ("Enable", "Disable"), f"Unexpected state {iface.state!r}"
        assert iface.flow_ctrl in ("Enable", "Disable"), f"Unexpected flow_ctrl {iface.flow_ctrl!r}"
        assert isinstance(iface.enabled, bool), f"enabled is not bool: {iface!r}"

    # Copper ports: Tw prefix, Auto speed/duplex
    copper = [i for i in interfaces if i.port.startswith("Tw")]
    assert len(copper) == 24, f"Expected 24 copper ports, got {len(copper)}"
    for iface in copper:
        assert iface.speed == "Auto", f"{iface.port}: expected Auto speed, got {iface.speed!r}"
        assert iface.duplex == "Auto", f"{iface.port}: expected Auto duplex, got {iface.duplex!r}"

    # SFP uplinks: Te prefix, 10G Full
    sfp = [i for i in interfaces if i.port.startswith("Te")]
    assert len(sfp) == 4, f"Expected 4 SFP ports, got {len(sfp)}"
    for iface in sfp:
        assert iface.speed == "10G",  f"{iface.port}: expected 10G speed, got {iface.speed!r}"
        assert iface.duplex == "Full", f"{iface.port}: expected Full duplex, got {iface.duplex!r}"

    # Port-name list (useful for ACL binding lookups)
    port_names = [i.port for i in interfaces]
    assert "Tw1/0/1"  in port_names, "Tw1/0/1 missing from port list"
    assert "Te1/0/25" in port_names, "Te1/0/25 missing from port list"
    assert "Te1/0/28" in port_names, "Te1/0/28 missing from port list"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    args = build_parser().parse_args()

    if args.verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            stream=sys.stdout,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        logging.getLogger("netmiko").setLevel(logging.DEBUG)

    params = {
        "host": args.host,
        "port": 22,
        "username": args.username,
        "password": args.password,
        "enable_password": args.enable_password,
    }

    print(f"Connecting to {args.host} …")
    with ConnectHandler(**build_device(FakeModule(params))) as net_connect:
        net_connect.enable()
        interfaces = get_interface_configuration(net_connect)

    print(f"\nParsed {len(interfaces)} interface(s):\n")
    print(f"  {'Port':<12} {'State':<10} {'Speed':<8} {'Duplex':<8} {'FlowCtrl':<10} {'Enabled':<8} Description")
    print(f"  {'-'*12} {'-'*10} {'-'*8} {'-'*8} {'-'*10} {'-'*8} {'-'*20}")
    for iface in interfaces:
        print(
            f"  {iface.port:<12} {iface.state:<10} {iface.speed:<8} "
            f"{iface.duplex:<8} {iface.flow_ctrl:<10} {str(iface.enabled):<8} "
            f"{iface.description or '—'}"
        )

    print(f"\nPort names:\n  {[i.port for i in interfaces]}")
    print(f"\nto_dict() (first port):\n  {json.dumps(interfaces[0].to_dict(), indent=4)}")

    try:
        check_interfaces(interfaces)
        print("\n✓ All live-test assertions passed.")
    except AssertionError as exc:
        print(f"\n✗ Assertion failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
