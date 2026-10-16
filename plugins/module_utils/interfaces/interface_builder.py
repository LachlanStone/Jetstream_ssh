"""Pure command builders for TP-Link JetStream interface configuration.

No Netmiko or Ansible imports — unit-testable without a device.
"""


# Maps the port_type YAML value to the CLI keyword the switch expects.
_PORT_TYPE_CLI = {
    "gigabitethernet": "gigabitEthernet",
    "gi":              "gigabitEthernet",
    "two-gigabitethernet": "two-gigabitEthernet",
    "tw":              "two-gigabitEthernet",
    "ten-gigabitethernet": "ten-gigabitEthernet",
    "te":              "ten-gigabitEthernet",
    "fastethernet":    "fastEthernet",
    "fa":              "fastEthernet",
}

_DEFAULT_PORT_TYPE = "gigabitEthernet"


def _port_name(port_id, port_type=None):
    """Return the full CLI interface token, e.g. 'gigabitEthernet 1/0/1'.

    Args:
        port_id (str): Port identifier, e.g. '1/0/1'.  Also accepts a
            fully-qualified form like 'gigabitEthernet 1/0/1', in which
            case ``port_type`` is ignored.
        port_type (str|None): One of the keys in ``_PORT_TYPE_CLI``
            (case-insensitive).  Defaults to 'gigabitEthernet' when None.

    Returns:
        str: Full CLI token ready to follow the ``interface`` keyword.

    Raises:
        ValueError: Unknown port_type value.
    """
    port_id = port_id.strip()
    # Already fully qualified — pass through unchanged.
    if " " in port_id:
        return port_id
    if port_type is None:
        return f"{_DEFAULT_PORT_TYPE} {port_id}"
    key = port_type.strip().lower()
    if key not in _PORT_TYPE_CLI:
        raise ValueError(
            f"Unknown port_type '{port_type}'. "
            f"Valid values: {sorted(_PORT_TYPE_CLI.keys())}"
        )
    return f"{_PORT_TYPE_CLI[key]} {port_id}"


def build_commands(iface):
    """Return an ordered list of CLI commands for one interface entry.

    Args:
        iface (dict): One element from the ``interfaces`` module param.
            Required key: ``name``.
            Optional keys: ``port_type``, ``speed``, ``enabled``,
                           ``description``, ``pvid``, ``vlans_untagged``,
                           ``vlans_tagged``, ``acceptable_frame_type``.

    Returns:
        list[str]: Commands ready to send inside config mode, without
                   ``configure`` or ``end`` — the caller handles those.

    Raises:
        ValueError: Unknown port_type value.
    """
    name = iface["name"]
    port_type = iface.get("port_type")

    cmds = [f"interface {_port_name(name, port_type)}"]

    # Admin state: True -> 'no shutdown', False -> 'shutdown', None -> leave as-is.
    enabled = iface.get("enabled")
    if enabled is False:
        cmds.append("shutdown")
    elif enabled is True:
        cmds.append("no shutdown")

    if "speed" in iface:
        speed = iface["speed"]
        if speed is None:
            cmds.append("no speed")
        else:
            cmds.append(f"speed {speed}")

    if "pvid" in iface:
        pvid = iface["pvid"]
        if pvid is None:
            cmds.append("no switchport pvid")
        else:
            cmds.append(f"switchport pvid {pvid}")

    vlans_untagged = iface.get("vlans_untagged") or []
    if vlans_untagged:
        vlan_str = ",".join(str(v) for v in vlans_untagged)
        cmds.append(f"switchport general allowed vlan {vlan_str} untagged")

    vlans_tagged = iface.get("vlans_tagged") or []
    if vlans_tagged:
        vlan_str = ",".join(str(v) for v in vlans_tagged)
        cmds.append(f"switchport general allowed vlan {vlan_str} tagged")

    vlans_disabled = iface.get("vlans_disabled") or []
    if vlans_disabled:
        vlan_str = ",".join(str(v) for v in vlans_disabled)
        cmds.append(f"no switchport general allowed vlan {vlan_str}")

    acceptable_frame = iface.get("acceptable_frame_type") or "all"
    if acceptable_frame != "all":
        cmds.append(f"switchport general acceptable-frame-type tagged-only")

    description = iface.get("description")
    if description:
        # Wrap in quotes only when the description contains spaces.
        if " " in description:
            cmds.append(f'description "{description}"')
        else:
            cmds.append(f"description {description}")
    if description is None:
        cmds.append("no description")

    # Return to global config context after each interface block.
    cmds.append("exit")

    return cmds
