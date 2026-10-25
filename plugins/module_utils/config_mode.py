"""Detect the current TP-Link JetStream CLI mode from the device prompt.

No Netmiko or Ansible imports — unit-testable without a device.
"""

import re
import time


# Prompt patterns. Order matters: interface patterns must come before the
# generic global-config pattern.
_MODE_PATTERNS = (
    ("interface-range", re.compile(r"\(config-if-range\)#\s*$")),
    ("interface", re.compile(r"\(config-if[^)]*\)#\s*$")),
    ("vlan", re.compile(r"\(config-vlan\)#\s*$")),
    ("global", re.compile(r"\(config\)#\s*$")),
    ("privileged", re.compile(r"#\s*$")),
    ("user", re.compile(r">\s*$")),
)

# Any configuration sub-mode (global, VLAN database, or interface).
CONFIG_PROMPT = r"\(config[^)]*\)#"
VLAN_CONFIG_PROMPT = r"\(config-vlan\)#"
INTERFACE_CONFIG_PROMPT = r"\(config-if[^)]*\)#"


def parse_config_mode(prompt):
    """Return the CLI mode for *prompt*.

    Args:
        prompt (str): Prompt such as ``switch(config-if)#``.

    Returns:
        str: One of ``interface-range``, ``interface``, ``vlan``,
             ``global``, ``privileged``, ``user``, or ``unknown``.
    """
    prompt = (prompt or "").strip()
    for mode, pattern in _MODE_PATTERNS:
        if pattern.search(prompt):
            return mode
    return "unknown"


def get_prompt(net_connect):
    """Return the current prompt, stripped."""
    return net_connect.find_prompt().strip()


def get_config_mode(net_connect):
    """Return the CLI mode for the live connection's current prompt."""
    return parse_config_mode(get_prompt(net_connect))


def is_in_config_interface(net_connect):
    """True when the connection is at an interface or interface-range prompt."""
    return get_config_mode(net_connect) in ("interface", "interface-range")


def ensure_global_config(net_connect, max_exits=4):
    """Return to global config mode from an interface/VLAN sub-mode.

    Sends ``exit`` once per sub-mode level. This also resynchronises the
    session after a bare ``exit`` sent with ``send_command_timing``.

    Raises:
        RuntimeError: The connection is not in config mode and cannot be
            moved to global config mode.
    """
    mode = get_config_mode(net_connect)
    exits = 0
    while mode in ("interface-range", "interface", "vlan"):
        if exits >= max_exits:
            break
        net_connect.send_command_timing("exit")
        exits += 1
        mode = get_config_mode(net_connect)

    if mode != "global":
        raise RuntimeError(
            f"Expected global config mode, got {mode!r} "
            f"(prompt {get_prompt(net_connect)!r})."
        )
    return mode


def require_config_mode(net_connect, expected, context="", attempts=5, delay=0.2):
    """Wait briefly for the live connection to enter *expected* config mode.

    The switch can take a moment to finish applying a context-entering
    command, so a single prompt read may still show the previous mode.

    Args:
        net_connect: Active Netmiko connection.
        expected (str): Mode name from ``parse_config_mode``.
        context (str): Optional label included in the error message.
        attempts (int): Prompt reads before reporting failure.
        delay (float): Seconds between prompt reads.

    Raises:
        RuntimeError: The current mode does not match *expected*.
    """
    mode = get_config_mode(net_connect)
    for _ in range(max(attempts, 1) - 1):
        if mode == expected:
            break
        time.sleep(delay)
        mode = get_config_mode(net_connect)

    if mode != expected:
        prefix = f"{context}: " if context else ""
        raise RuntimeError(
            f"{prefix}expected {expected} config mode, got {mode!r} "
            f"(prompt {get_prompt(net_connect)!r})."
        )
    return mode
