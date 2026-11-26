"""Parse TP-Link JetStream CLI output into interface state objects.

``show interface configuration`` → :class:`InterfaceConfig`.
``show running-config`` → :class:`RunningConfigInterface`.
"""

import logging
import re

from ansible_collections.lachlanstone.jetstream.plugins.module_utils.interfaces.interface_classes import (
    InterfaceConfig,
    RunningConfigInterface,
)

logger = logging.getLogger(__name__)

# Matches a port identifier prefix: Tw, Te, Gi, Fa, Hu, etc.
_PORT_PREFIX_RE = re.compile(r"^[A-Za-z]+\d+/")


def parse_interface_configuration(output: str) -> list:
    """Parse ``show interface configuration`` output into a list of :class:`InterfaceConfig`.

    The command produces a fixed-column table::

        SG3428X-M2#show interface configuration
         Port      State       Speed     Duplex    FlowCtrl    Description
         ----      -----       -----     ------    --------    -----------
         Tw1/0/1   Enable      Auto      Auto      Disable
         Te1/0/25  Enable      10G       Full      Disable     Uplink

    Lines are included only when the first token matches the port-identifier
    pattern (letter prefix + digits + slash), so header, separator, and prompt
    lines are skipped automatically.

    Args:
        output: Raw string returned by the switch for ``show interface configuration``.

    Returns:
        List of :class:`InterfaceConfig`, one per data row.
    """
    interfaces = []

    for raw in output.splitlines():
        line = raw.strip()
        if not line:
            continue

        fields = line.split()
        if not fields:
            continue

        # Only process rows whose first token looks like a port identifier.
        if not _PORT_PREFIX_RE.match(fields[0]):
            continue

        try:
            iface = InterfaceConfig.from_parsed_line(fields)
            interfaces.append(iface)
        except ValueError as exc:
            logger.warning("Skipping unparseable interface line %r: %s", line, exc)

    logger.info("Parsed %d interface(s) from 'show interface configuration'.", len(interfaces))
    return interfaces


def get_interface_configuration(net_connect) -> list:
    """Run ``show interface configuration`` on the device and return parsed results.

    Args:
        net_connect: Active Netmiko connection (enable mode, not config mode).

    Returns:
        List of :class:`InterfaceConfig`.
    """
    from ansible_collections.lachlanstone.jetstream.plugins.module_utils.send_command import (
        send_command,
    )

    output = send_command(net_connect, cmd="show interface configuration", retries=1)
    return parse_interface_configuration(output)


def get_running_config(net_connect) -> list:
    """Run ``show running-config`` on the device and return parsed physical interfaces.

    Args:
        net_connect: Active Netmiko connection (enable mode, not config mode).

    Returns:
        List of :class:`RunningConfigInterface`, one per physical interface block.
    """
    from ansible_collections.lachlanstone.jetstream.plugins.module_utils.send_command import (
        send_command,
    )

    output = send_command(net_connect, cmd="show running-config", retries=1)
    return parse_running_config(output)


# ---------------------------------------------------------------------------
# ``show running-config`` parsing
# ---------------------------------------------------------------------------

# Interface types that are physical ports rather than ``vlan``/L3 blocks.
_PHYSICAL_TYPE_RE = re.compile(r"^[a-z-]*ethernet$")


def _parse_vlan_list(token: str) -> list:
    """Expand a VLAN token into a list of ints.

    Accepts single IDs (``11``), comma lists (``10,11,12``) and dash ranges
    (``10-12``), including mixtures (``10-12,15``).
    """
    result = []
    for part in token.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, _, end = part.partition("-")
            result.extend(range(int(start), int(end) + 1))
        else:
            result.append(int(part))
    return result


def _unquote(value: str) -> str:
    """Strip a single pair of surrounding double quotes, if present."""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def _apply_subcommand(iface: "RunningConfigInterface", line: str) -> None:
    """Apply one indented subcommand line to the current interface."""
    parts = line.split()

    # switchport pvid <id> / no switchport pvid
    if len(parts) == 3 and parts[:2] == ["switchport", "pvid"]:
        iface.pvid = int(parts[2])
        return
    if line == "no switchport pvid":
        iface.pvid = None
        return

    # switchport general allowed vlan <list> untagged|tagged
    if (
        len(parts) == 6
        and parts[:4] == ["switchport", "general", "allowed", "vlan"]
        and parts[5] in ("untagged", "tagged")
    ):
        vlans = _parse_vlan_list(parts[4])
        if parts[5] == "untagged":
            iface.vlans_untagged.extend(vlans)
        else:
            iface.vlans_tagged.extend(vlans)
        return

    # no switchport general allowed vlan <list>
    if (
        len(parts) == 6
        and parts[:5] == ["no", "switchport", "general", "allowed", "vlan"]
    ):
        iface.vlans_disabled.extend(_parse_vlan_list(parts[5]))
        return

    # Acceptable frame type — running-config form and builder form.
    if line in ("switchport acceptable frame tagged",
                "switchport general acceptable-frame-type tagged-only"):
        iface.acceptable_frame_type = "tagged"
        return
    if line in ("switchport acceptable frame all",
                "switchport general acceptable-frame-type all"):
        iface.acceptable_frame_type = "all"
        return

    # Description
    if line == "no description":
        iface.description = ""
        return
    if line.startswith("description "):
        iface.description = _unquote(line[len("description "):])
        return

    # ``spanning-tree`` and anything else is not part of the stored state.


def parse_running_config(output: str) -> list:
    """Parse ``show running-config`` output into :class:`RunningConfigInterface` objects.

    Handles both the full ``show running-config`` output and the single-interface
    form ``show running-config interface <type> <name>``, which share the same
    block grammar::

        interface two-gigabitEthernet 1/0/1
          switchport general allowed vlan 11 untagged
          switchport general allowed vlan 10 tagged
          switchport acceptable frame tagged
          no switchport general allowed vlan 1
          spanning-tree

    Only physical ``*-Ethernet`` blocks are collected; ``interface vlan N`` and
    all global configuration lines are skipped.

    Args:
        output: Raw string returned by the switch for ``show running-config``
            (full or single-interface).

    Returns:
        List of :class:`RunningConfigInterface`, one per physical interface block.
    """
    interfaces = []
    current = None

    for raw in output.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            continue

        # ``interface <type> <name>`` starts a new block.
        if stripped.startswith("interface "):
            current = None
            parts = stripped.split()
            if len(parts) >= 3 and _PHYSICAL_TYPE_RE.match(parts[1].lower()):
                current = RunningConfigInterface(
                    name=parts[2],
                    port_type=parts[1],
                )
                interfaces.append(current)
            continue

        # ``end`` terminates the configuration.
        if stripped == "end":
            current = None
            continue

        # Only indented lines belong to the current interface block.
        if current is not None and line[:1] in (" ", "\t"):
            _apply_subcommand(current, stripped)

    logger.info("Parsed %d physical interface(s) from 'show running-config'.", len(interfaces))
    return interfaces
