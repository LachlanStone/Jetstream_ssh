#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Dev harness for the interface configuration parser.

Run this file directly to exercise ``parse_interface_configuration`` and
``InterfaceConfig`` against the hardcoded sample output from a real switch.
No SSH connection required.

Usage::

    python3 plugins/modules/jetstream_interfaces_dev.py
"""

import sys
import os

# ---------------------------------------------------------------------------
# Path bootstrap — allows running from the repo root without installing the
# collection.  Inserts the ancestor directory that contains the
# `ansible_collections` namespace so Python can resolve the imports.
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..")
)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from ansible_collections.lachlanstone.jetstream.plugins.module_utils.interfaces.interface_classes import (
    InterfaceConfig,
)
from ansible_collections.lachlanstone.jetstream.plugins.module_utils.interfaces.interface_parsers import (
    parse_interface_configuration,
)


# ---------------------------------------------------------------------------
# Sample output captured from a real SG3428X-M2
# ---------------------------------------------------------------------------
SAMPLE_OUTPUT = """\
SG3428X-M2#show interface configuration
 Port      State       Speed     Duplex    FlowCtrl    Description
 ----      -----       -----     ------    --------    -----------
 Tw1/0/1   Enable      Auto      Auto      Disable
 Tw1/0/2   Enable      Auto      Auto      Disable
 Tw1/0/3   Enable      Auto      Auto      Disable
 Tw1/0/4   Enable      Auto      Auto      Disable
 Tw1/0/5   Enable      Auto      Auto      Disable
 Tw1/0/6   Enable      Auto      Auto      Disable
 Tw1/0/7   Enable      Auto      Auto      Disable
 Tw1/0/8   Enable      Auto      Auto      Disable
 Tw1/0/9   Enable      Auto      Auto      Disable
 Tw1/0/10  Enable      Auto      Auto      Disable
 Tw1/0/11  Enable      Auto      Auto      Disable
 Tw1/0/12  Enable      Auto      Auto      Disable
 Tw1/0/13  Enable      Auto      Auto      Disable
 Tw1/0/14  Enable      Auto      Auto      Disable
 Tw1/0/15  Enable      Auto      Auto      Disable
 Tw1/0/16  Enable      Auto      Auto      Disable
 Tw1/0/17  Enable      Auto      Auto      Disable
 Tw1/0/18  Enable      Auto      Auto      Disable
 Tw1/0/19  Enable      Auto      Auto      Disable
 Tw1/0/20  Enable      Auto      Auto      Disable
 Tw1/0/21  Enable      Auto      Auto      Disable
 Tw1/0/22  Enable      Auto      Auto      Disable
 Tw1/0/23  Enable      Auto      Auto      Disable
 Tw1/0/24  Enable      Auto      Auto      Disable
 Te1/0/25  Enable      10G       Full      Disable
 Te1/0/26  Enable      10G       Full      Disable
 Te1/0/27  Enable      10G       Full      Disable
 Te1/0/28  Enable      10G       Full      Disable
"""


def main():
    print("=" * 60)
    print("jetstream_interfaces_dev — interface configuration parser")
    print("=" * 60)

    interfaces = parse_interface_configuration(SAMPLE_OUTPUT)

    print(f"\nParsed {len(interfaces)} interface(s):\n")
    print(f"  {'Port':<12} {'State':<10} {'Speed':<8} {'Duplex':<8} {'FlowCtrl':<10} {'Enabled':<8} Description")
    print(f"  {'-'*12} {'-'*10} {'-'*8} {'-'*8} {'-'*10} {'-'*8} {'-'*20}")
    for iface in interfaces:
        print(
            f"  {iface.port:<12} {iface.state:<10} {iface.speed:<8} "
            f"{iface.duplex:<8} {iface.flow_ctrl:<10} {str(iface.enabled):<8} "
            f"{iface.description or '—'}"
        )

    print(f"\nPort names (for ACL state lookup):")
    port_names = [iface.port for iface in interfaces]
    print(f"  {port_names}")

    print(f"\nto_dict() sample (first port):")
    if interfaces:
        import json
        print(f"  {json.dumps(interfaces[0].to_dict(), indent=4)}")

    print(f"\nfrom_dict() round-trip check:")
    sample = {
        "port": "Te1/0/25",
        "state": "Enable",
        "speed": "10G",
        "duplex": "Full",
        "flow_ctrl": "Disable",
        "description": "Uplink",
    }
    rebuilt = InterfaceConfig.from_dict(sample)
    print(f"  {rebuilt!r}")
    assert rebuilt.enabled is True, "enabled flag derivation failed"
    print("  ✓ enabled flag correctly derived from state")

    print(f"\n{'=' * 60}")
    print(f"All checks passed. {len(interfaces)} interface(s) parsed successfully.")


if __name__ == "__main__":
    main()
