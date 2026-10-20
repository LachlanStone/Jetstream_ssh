"""Parse Omada ACL CLI output and map protocol names to numbers."""

from plugins.module_utils.send_command import send_command
import logging

logger = logging.getLogger(__name__)


def get_bound_access_lists(net_connect):
    """Return ACLs currently bound on the device.

    Runs ``show access-list bind``. Drops blank lines and any line that
    still contains ``#`` (prompt/command echo that ``strip_command``
    sometimes leaves behind).

    Args:
        net_connect: Active Netmiko connection.

    Returns:
        dict: ``{acl_id: row}`` keyed by ``ACL ID``. Empty if none are bound.
    """
    output = send_command(net_connect, cmd="show access-list bind")

    lines = [line for line in output.splitlines() if line.strip() and "#" not in line]

    if len(lines) < 3:
        logger.info("No ACLs are currently bound to any interfaces.")
        return {}

    headers = [h.strip() for h in lines[0].split("  ") if h.strip()]
    result = []

    for line in lines[2:]:
        parts = [p.strip() for p in line.split("  ") if p.strip()]
        result.append(dict(zip(headers, parts)))

    bound_acls = {entry.get("ACL ID"): entry for entry in result if entry.get("ACL ID") is not None}
    return bound_acls


def get_current_acls(net_connect):
    """Return ACLs defined on the device.

    Runs ``show access-list``. Parses Combined and IP ACL headers and
    their ``rule`` lines. Optional ``logging`` on a rule is captured
    when present.

    Args:
        net_connect: Active Netmiko connection.

    Returns:
        dict: ``{acl_id: {id, name, type, rules}}``.
    """
    output = send_command(net_connect, cmd="show access-list")
    acls = {}
    current_acl = None
    for raw in output.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("Combined access list") or line.startswith("IP access list"):
            parts = line.split()
            acl_type = parts[0].lower()
            acl_id = parts[3]
            name_part = line.split("name:", 1)[1].strip()
            acl_name = name_part.strip('"')

            current_acl = {
                "id": acl_id,
                "name": acl_name,
                "type": acl_type,
                "rules": []
            }
            acls[acl_id] = current_acl
            continue
        elif line.startswith("rule") and current_acl:
            parts = line.split()
            seq = int(parts[1])
            action = parts[2]
            rule = {
                "seq": seq,
                "action": action
            }

            if "logging" in parts:
                idx = parts.index("logging")
                rule["logging"] = parts[idx + 1]
            current_acl["rules"].append(rule)
    logger.info(f"Current ACLs on device: {acls}")
    return acls


protocol_map = {
    "ICMP": 1,
    "IGMP": 2,
    "TCP": 6,
    "UDP": 17,
    "IPV6": 41,
    "ESP": 50,
    "AH": 51,
    "OSPF": 89,
}
"""IP protocol name (upper-case) to number."""


def get_protocol_number(protocol_name):
    """Return the IANA number for *protocol_name*.

    Matching is case-insensitive. Raises ``ValueError`` if the name is
    not a string or is not in :data:`protocol_map`.
    """
    if not isinstance(protocol_name, str):
        raise ValueError("Protocol name must be a string.")
    normalized_name = protocol_name.strip().upper()
    if normalized_name not in protocol_map:
        raise ValueError(f"Unknown protocol name: {protocol_name}")
    return protocol_map[normalized_name]


def protocol_names():
    """Return the known protocol names (keys of :data:`protocol_map`)."""
    return list(protocol_map.keys())
