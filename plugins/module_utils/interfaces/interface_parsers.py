"""Parse ``show interface configuration`` CLI output into InterfaceConfig objects."""

import logging
import re

from ansible_collections.lachlanstone.jetstream.plugins.module_utils.interfaces.interface_classes import (
    InterfaceConfig,
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
