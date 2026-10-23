"""Pure command builders for TP-Link JetStream VLAN configuration.

No Netmiko or Ansible imports — unit-testable without a device.
"""


def build_vlan_commands(vlan):
    """Return an ordered list of CLI commands for one VLAN entry.

    Args:
        vlan (dict): One element from the ``vlans`` module param.
            Required key: ``vlan_id``.
            Optional keys: ``name``, ``ip_address``, ``subnet_mask``,
                           ``ip_dhcp``.

    Returns:
        list[str]: Commands ready to send inside config mode, without
                   ``configure`` or ``end`` — the caller handles those.

    Raises:
        ValueError: vlan_id out of range, ip_address and ip_dhcp both set,
            or ip_address set without subnet_mask.
    """
    vlan_id = vlan["vlan_id"]

    if not 1 <= vlan_id <= 4094:
        raise ValueError(f"vlan_id {vlan_id} is out of range (1-4094).")

    name = vlan.get("name")
    ip_address = vlan.get("ip_address")
    subnet_mask = vlan.get("subnet_mask")
    ip_dhcp = vlan.get("ip_dhcp")

    if ip_address and ip_dhcp:
        raise ValueError(
            f"VLAN {vlan_id}: ip_address and ip_dhcp are mutually exclusive."
        )
    if ip_address and not subnet_mask:
        raise ValueError(
            f"VLAN {vlan_id}: subnet_mask is required when ip_address is set."
        )

    cmds = [f"vlan {vlan_id}"]

    if name is not None:
        cmds.append(f"name {name}")

    # Close the VLAN database context before entering the SVI context.
    cmds.append("exit")

    if ip_address or ip_dhcp:
        cmds.append(f"interface vlan {vlan_id}")

        if ip_address:
            cmds.append(f"ip address {ip_address} {subnet_mask}")
        elif ip_dhcp:
            cmds.append("ip address-alloc dhcp")

        cmds.append("exit")

    return cmds
