"""Parse Omada ``show running-config`` output for VLAN and SVI state."""

import re

from ansible_collections.lachlanstone.jetstream.plugins.module_utils.send_command import (
    send_command,
)


def _new_vlan(vlan_id):
    return {
        "vlan_id": vlan_id,
        "name": None,
        "ip_address": None,
        "subnet_mask": None,
        "ip_dhcp": False,
    }


def _expand_vlan_ids(spec):
    """Expand ``10``, ``10-12`` or ``10,20-21`` into a list of ints."""
    ids = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            ids.extend(range(int(start), int(end) + 1))
        else:
            ids.append(int(part))
    return ids


def parse_running_config_vlans(output):
    """Parse VLAN and SVI state from ``show running-config``.

    Only the forms observed on an SG3428X-M2 are recognised:

    - ``vlan 1`` and ``vlan 10-11`` (top-level VLAN database entries)
    - `` name "System-VLAN"`` (indented, applies to the last VLAN entry)
    - ``interface vlan 10`` (top-level SVI block)
    - `` ip address 10.10.10.50 255.255.255.0``
    - `` ip address-alloc dhcp``

    Returns:
        dict[int, dict]: ``{vlan_id: {vlan_id, name, ip_address,
        subnet_mask, ip_dhcp}}``.
    """
    vlans = {}
    current_vlan_ids = []
    current_svi = None

    for raw in output.splitlines():
        line = raw.strip()
        if not line or line.startswith("!") or line == "#":
            continue

        top_level = not raw[:1].isspace()

        if top_level:
            current_vlan_ids = []
            current_svi = None

            match = re.match(r"^vlan\s+([\d,\-]+)$", line)
            if match:
                for vlan_id in _expand_vlan_ids(match.group(1)):
                    vlans.setdefault(vlan_id, _new_vlan(vlan_id))
                    current_vlan_ids.append(vlan_id)
                continue

            match = re.match(r"^interface\s+vlan\s+(\d+)$", line)
            if match:
                current_svi = int(match.group(1))
                vlans.setdefault(current_svi, _new_vlan(current_svi))
            continue

        if current_vlan_ids:
            match = re.match(r'^name\s+(.+)$', line)
            if match:
                name = match.group(1).strip().strip('"')
                for vlan_id in current_vlan_ids:
                    vlans[vlan_id]["name"] = name
                continue

        if current_svi is not None:
            match = re.match(r"^ip\s+address\s+(\S+)\s+(\S+)$", line)
            if match:
                vlans[current_svi]["ip_address"] = match.group(1)
                vlans[current_svi]["subnet_mask"] = match.group(2)
                continue

            if re.match(r"^ip\s+address-alloc\s+dhcp$", line):
                vlans[current_svi]["ip_dhcp"] = True

    return vlans


def get_current_vlans(net_connect):
    """Read and parse VLAN/SVI state from ``show running-config``.

    Raises:
        RuntimeError: The output contained no parseable VLAN. VLAN 1 always
            exists, so an empty result means the read failed; applying changes
            from an unknown state would not be safe.
    """
    output = send_command(net_connect, cmd="show running-config", retries=1)
    vlans = parse_running_config_vlans(output)
    if not vlans:
        raise RuntimeError(
            "Could not read VLAN state from 'show running-config'; "
            "refusing to apply changes."
        )
    return vlans
