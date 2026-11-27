#!/usr/bin/python
# -*- coding: utf-8 -*-
# MIT License (see LICENSE)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: jetstream_system
short_description: Manage general system settings on TP-Link JetStream switches
description:
  - Connects to a TP-Link JetStream (Omada) switch over SSH with Netmiko and applies general system
    configuration such as hostname, location, contact and DNS servers.
  - Commands are sent through the switch CLI, so the controller running the module needs network access to
    the switch.
version_added: "0.1.0"
author:
  - Lachlan Stone (@lachlanstone)
requirements:
  - netmiko
options:
  host:
    description: Hostname or IP address of the switch.
    type: str
    required: true
  port:
    description: SSH port of the switch.
    type: int
    default: 22
  username:
    description: SSH username.
    type: str
    required: true
  password:
    description: SSH password.
    type: str
    default: ""
  enable_password:
    description: Password for privileged (enable) mode.
    type: str
    default: ""
  read_timeout:
    description:
      - Seconds Netmiko waits for the command prompt before raising a read timeout.
      - Defaults to C(JETSTREAM_READ_TIMEOUT) when set, otherwise 30.
    type: float
  system:
    description: General system information.
    type: dict
    suboptions:
      hostname:
        description: Switch hostname.
        type: str
      location:
        description: System location string.
        type: str
      contact:
        description: System contact string.
        type: str
  lldp:
    description: LLDP (Link Layer Discovery Protocol) configuration.
    type: dict
    suboptions:
      enabled:
        description: Enable or disable LLDP globally on the switch.
        type: bool
  dns:
    description: DNS server settings.
    type: dict
    suboptions:
      primary:
        description: Primary DNS server address.
        type: str
      secondary:
        description: Secondary DNS server address.
        type: str
  ntp:
    description:
      - NTP settings.
      - Applied when C(type) is set to V(ntp), C(ntp_utc), at least 2 servers in C(ntp_servers), and C(ntp_fetch_time) are all provided.
    type: dict
    suboptions:
      type:
        description: NTP mode. Must be set to V(ntp) to apply.
        type: str
      ntp_utc:
        description: UTC offset used for NTP time (e.g., V(+00:00) or V(+10:00)).
        type: str
      ntp_servers:
        description: List of NTP servers (minimum 2 servers, up to 5).
        type: list
        elements: str
        default: []
      ntp_fetch_time:
        description: Interval in minutes at which the switch polls NTP servers.
        type: int
notes:
  - Supports check mode. Current state is read first, so check mode reports C(changed: true) only when the switch differs from the requested settings.
  - Only the blocks you supply are read and compared; an unreadable or unparsed state falls back to applying the requested values.
"""

EXAMPLES = r"""
- name: Set hostname, location and contact
  lachlanstone.jetstream.jetstream_system:
    host: 192.0.2.10
    username: admin
    password: "{{ vault_switch_password }}"
    enable_password: "{{ vault_switch_enable_password }}"
    system:
      hostname: switch-01
      location: Server Room
      contact: admin@example.com

- name: Configure DNS servers
  lachlanstone.jetstream.jetstream_system:
    host: 192.0.2.10
    username: admin
    password: "{{ vault_switch_password }}"
    enable_password: "{{ vault_switch_enable_password }}"
    dns:
      primary: 192.0.2.53
      secondary: 198.51.100.53

- name: Configure NTP synchronization
  lachlanstone.jetstream.jetstream_system:
    host: 192.0.2.10
    username: admin
    password: "{{ vault_switch_password }}"
    enable_password: "{{ vault_switch_enable_password }}"
    ntp:
      type: ntp
      ntp_utc: "+00:00"
      ntp_servers:
        - 192.0.2.123
        - 198.51.100.123
      ntp_fetch_time: 60

- name: Enable global LLDP
  lachlanstone.jetstream.jetstream_system:
    host: 192.0.2.10
    username: admin
    password: "{{ vault_switch_password }}"
    enable_password: "{{ vault_switch_enable_password }}"
    lldp:
      enabled: true
"""

RETURN = r"""
msg:
  description: Summary message.
  returned: always
  type: str
switch:
  description: Host the module connected to.
  returned: always
  type: str
changed:
  description: Whether any configuration command was sent (or would be sent, in check mode).
  returned: always
  type: bool
check_mode:
  description: Whether the module ran in check mode.
  returned: always
  type: bool
cmd:
  description: Last command sent to the switch.
  returned: always
  type: str
steps:
  description: Per-step results; more detail is returned at higher Ansible verbosity.
  returned: always
  type: list
  elements: dict
"""

import logging
import re
import traceback
from ansible.module_utils.basic import AnsibleModule
from netmiko import ConnectHandler

from ansible_collections.lachlanstone.jetstream.plugins.module_utils.send_command import (
    send_command,
)

from ansible_collections.lachlanstone.jetstream.plugins.module_utils.collector import (
    ResultCollector,
)
from ansible_collections.lachlanstone.jetstream.plugins.module_utils.device import (
    build_device,
)


# Component: Configure logging for Netmiko
logger = logging.getLogger(name="netmiko")
logger.setLevel(level=logging.DEBUG)
logger.propagate = False
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
# Component: StreamHandler (logger.info debug messages to console)
logging_enabled = True  # Set this to False to disable console logging
if logging_enabled and not logger.handlers:
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level=logging.INFO)
    stream_handler.setFormatter(fmt=formatter)
    logger.addHandler(hdlr=stream_handler)

def parse_system_info(output):
    """Parse ``show system-info`` output into ``hostname``/``location``/``contact``.

    The switch prints ``Key - value`` lines (see
    ``extras/ntc_templates/templates/tplink_jetstream_show_system-info.textfsm``);
    ``Key: value`` lines are accepted too.  Lines that carry neither a
    recognised key nor a value are ignored.
    """
    info = {}
    if not output:
        return info

    for line in output.splitlines():
        parts = re.split(r"\s+-\s*|\s*:\s*", line, maxsplit=1)
        if len(parts) != 2:
            continue
        key = parts[0].strip().lower().replace(" ", "_")
        value = parts[1].strip()
        if not value:
            continue
        if key in ("hostname", "host_name", "system_name", "name"):
            info["hostname"] = value
        elif key in ("location", "system_location"):
            info["location"] = value
        elif key in ("contact", "system_contact", "contact_information"):
            info["contact"] = value
    return info


def read_system_info(net_connect):
    """Read current system info from the switch via ``show system-info``.

    Returns a dict with any of ``hostname``/``location``/``contact`` that
    could be parsed from the output.  Returns an empty dict when the command
    fails or nothing recognizable is parsed, in which case callers fall back
    to applying the desired config (the current, safe behavior).
    """
    if net_connect is None:
        return {}

    try:
        output = send_command(net_connect, cmd="show system-info")
    except Exception:  # pragma: no cover - defensive; switch may reject the command
        logger.info("Unable to read current system info; applying desired config.")
        return {}

    if not isinstance(output, str):
        return {}
    return parse_system_info(output)


def parse_running_config(output):
    """Parse ``show running-config`` output into current DNS, NTP and LLDP state.

    Recognised keys: ``dns_primary``, ``dns_secondary``, ``ntp_utc``,
    ``ntp_servers``, ``ntp_fetch_time`` and ``lldp_enabled`` (only when the
    config states it; an absent LLDP line stays ``None`` = unknown).
    """
    config = {}
    if not output:
        return config

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if line.startswith("ip dns-address "):
            tokens = line.split()
            if len(tokens) >= 4 and tokens[2] == "primary":
                config["dns_primary"] = tokens[3]
                if "secondary" in tokens:
                    index = tokens.index("secondary")
                    if index + 1 < len(tokens):
                        config["dns_secondary"] = tokens[index + 1]
        elif line.startswith("system-time ntp "):
            tokens = line.split()
            if len(tokens) >= 6:
                # system-time ntp <utc> <s1> <s2> <fetch> [<s3> <s4> <s5>]
                config["ntp_utc"] = tokens[2]
                config["ntp_servers"] = tokens[3:5] + tokens[6:9]
                config["ntp_fetch_time"] = tokens[5]
        elif line in ("lldp", "lldp run"):
            config["lldp_enabled"] = True
        elif line in ("no lldp", "no lldp run"):
            config["lldp_enabled"] = False
    return config


def read_running_config(net_connect):
    """Read current DNS, NTP and LLDP state from ``show running-config``.

    Returns an empty dict when the command fails or nothing is parsed, in
    which case callers fall back to applying the desired config.
    """
    if net_connect is None:
        return {}

    try:
        output = send_command(net_connect, cmd="show running-config", retries=1)
    except Exception:  # pragma: no cover - defensive; switch may reject the command
        logger.info("Unable to read running-config; applying desired config.")
        return {}

    if not isinstance(output, str):
        return {}
    return parse_running_config(output)


def normalize_utc_offset(value):
    """Canonicalise a UTC offset so ``UTC``, ``GMT``, ``+00:00`` compare equal."""
    if value is None:
        return ""
    text = str(value).strip()
    if text.upper() in ("UTC", "GMT"):
        return "+00:00"
    match = re.match(r"^(?:UTC|GMT)?\s*([+-]?)(\d{1,2}):?(\d{2})?$", text, re.IGNORECASE)
    if not match:
        return text.upper()
    sign = match.group(1) or "+"
    hours = int(match.group(2))
    minutes = int(match.group(3) or 0)
    if hours == 0 and minutes == 0:
        return "+00:00"
    return f"{sign}{hours:02d}:{minutes:02d}"


def set_general_information(net_connect, system, collector, check_mode=False, current_system=None):
    """Set general information on the switch (hostname, location, contact).

    Args:
        check_mode: When True, report what *would* change without sending
            commands to the device.
        current_system: Optional pre-read state from :func:`read_system_info`;
            read lazily when omitted. An empty dict means "unknown", which
            falls back to applying the desired value.
    """
    system = system or {}
    changed = False
    params_to_commands: dict[str, str] = {
        "hostname": "hostname",
        "location": "location",
        "contact": "contact-info",
    }
    commands = []
    commands_sent = []
    has_desired = any(system.get(param) for param in params_to_commands)

    if current_system is None:
        # Read-only, so it runs in check mode too: that is what lets check
        # mode report an already-matching switch as unchanged.
        current_system = read_system_info(net_connect) if has_desired else {}

    for param, cmd_prefix in params_to_commands.items():
        value = system.get(param)
        if not value:
            logger.info("No %s provided, skipping %s configuration.", param, param)
            continue

        if current_system.get(param) == value:
            logger.info("%s already set to %s, skipping.", param, value)
            continue

        cmd = f"{cmd_prefix} {value}"
        if check_mode:
            logger.info("Check mode: would set %s with command: %s", param, cmd)
        else:
            logger.info("Setting %s with command: %s", param, cmd)
            send_command(net_connect, cmd=cmd)
            commands_sent.append(cmd)
        commands.append(cmd)
        changed = True

    if changed:
        msg = f"Configured system info: hostname={system.get('hostname')}, location={system.get('location')}, contact={system.get('contact')}"
    elif has_desired:
        msg = "System info already matches the switch, nothing to configure"
    else:
        msg = "No system info provided, nothing to configure"

    collector.add_step(
        name=set_general_information.__name__,
        step_result={
            "changed": changed,
            "msg": msg,
            "commands": commands,
            "commands_sent": [] if check_mode else commands_sent,
            "system_info": system,
            "hostname": system.get("hostname"),
            "location": system.get("location"),
            "contact": system.get("contact"),
        },
    )

def configure_dns(net_connect, dns, collector, check_mode=False, current_config=None):
    """Configure DNS servers on the switch.

    Args:
        check_mode: When True, report what *would* change without sending
            commands to the device.
        current_config: Optional pre-read state from :func:`read_running_config`;
            read lazily when omitted. An empty dict means "unknown", which
            falls back to applying the desired config.
    """
    if not dns:
        return

    primary = dns.get("primary")
    secondary = dns.get("secondary")

    if secondary and not primary:
        collector.add_step(
            name=configure_dns.__name__,
            step_result={
                "changed": False,
                "msg": "DNS configuration requires 'primary' server when 'secondary' is specified.",
                "success": False,
            },
        )
        return

    if primary:
        cmd = f"ip dns-address primary {primary}"
        if secondary:
            msg = f"Configuring DNS: primary={primary}, secondary={secondary}"
            cmd += f" secondary {secondary}"
        else:
            msg = f"Configuring DNS: primary={primary}, no secondary provided"

        if current_config is None:
            current_config = read_running_config(net_connect)

        matches = current_config.get("dns_primary") == primary and (
            not secondary or current_config.get("dns_secondary") == secondary
        )
        if matches:
            logger.info("DNS already configured (%s), skipping.", cmd)
            collector.add_step(
                name=configure_dns.__name__,
                step_result={
                    "changed": False,
                    "msg": f"DNS already configured: primary={primary}"
                    + (f", secondary={secondary}" if secondary else ""),
                    "commands": [],
                    "commands_sent": [],
                },
            )
            return

        if check_mode:
            logger.info("Check mode: %s", msg)
        else:
            logger.info("%s", msg)
            send_command(net_connect, cmd=cmd)
        collector.add_step(
            name=configure_dns.__name__,
            step_result={
                "changed": True,
                "msg": msg,
                "commands": [cmd],
                "commands_sent": [] if check_mode else [cmd],
            },
        )

def configure_ntp(net_connect, ntp, collector, check_mode=False, current_config=None):
    """Configure NTP on the switch.

    Args:
        check_mode: When True, report what *would* change without sending
            commands to the device.
        current_config: Optional pre-read state from :func:`read_running_config`;
            read lazily when omitted. An empty dict means "unknown", which
            falls back to applying the desired config.
    """
    if not ntp or not ntp.get("type"):
        return

    if ntp.get("type") != "ntp":
        logger.info("NTP type is '%s' (not 'ntp'), skipping NTP configuration.", ntp.get("type"))
        return

    utc = ntp.get("ntp_utc")
    if not utc:
        collector.add_step(
            name=configure_ntp.__name__,
            step_result={
                "changed": False,
                "msg": "NTP configuration requires 'ntp_utc' (e.g., '+00:00').",
                "success": False,
            },
        )
        return

    ntp_servers = ntp.get("ntp_servers") or []
    if len(ntp_servers) < 2:
        collector.add_step(
            name=configure_ntp.__name__,
            step_result={
                "changed": False,
                "msg": f"NTP configuration on TP-Link JetStream CLI requires at least 2 servers in 'ntp_servers' (got {len(ntp_servers)}).",
                "success": False,
            },
        )
        return

    fetch_time = ntp.get("ntp_fetch_time")
    if fetch_time is None:
        collector.add_step(
            name=configure_ntp.__name__,
            step_result={
                "changed": False,
                "msg": "NTP configuration requires 'ntp_fetch_time' (polling interval in minutes).",
                "success": False,
            },
        )
        return

    cmd_parts = [
        "system-time",
        "ntp",
        utc,
        *ntp_servers[:2],
        str(fetch_time),
        *ntp_servers[2:5],
    ]
    cmd = " ".join(cmd_parts)

    if current_config is None:
        current_config = read_running_config(net_connect)

    already_configured = (
        normalize_utc_offset(current_config.get("ntp_utc")) == normalize_utc_offset(utc)
        and current_config.get("ntp_servers") == ntp_servers[:5]
        and current_config.get("ntp_fetch_time") == str(fetch_time)
    )
    if already_configured:
        logger.info("NTP already configured (%s), skipping.", cmd)
        collector.add_step(
            name=configure_ntp.__name__,
            step_result={
                "changed": False,
                "msg": f"NTP already configured: servers={ntp_servers}, fetch_time={fetch_time}",
                "commands": [],
                "commands_sent": [],
            },
        )
        return

    if check_mode:
        logger.info("Check mode: would configure NTP: %s", cmd)
    else:
        logger.info("Configuring NTP: %s", cmd)
        send_command(net_connect, cmd=cmd)
    collector.add_step(
        name=configure_ntp.__name__,
        step_result={
                "changed": True,
                "msg": f"Configuring NTP: servers={ntp_servers}, fetch_time={fetch_time}",
                "commands": [cmd],
                "commands_sent": [] if check_mode else [cmd],
            },
        )

def configure_lldp(net_connect, lldp, collector, check_mode=False, current_config=None):
    """Configure LLDP on the switch.

    Args:
        check_mode: When True, report what *would* change without sending
            commands to the device.
        current_config: Optional pre-read state from :func:`read_running_config`;
            read lazily when omitted. An empty dict means "unknown", which
            falls back to applying the desired config.
    """
    if not lldp or lldp.get("enabled") is None:
        logger.info("No LLDP configuration provided, skipping.")
        return

    enabled = lldp.get("enabled")
    cmd = "lldp run" if enabled else "no lldp run"
    msg = f"Configuring LLDP: enabled={enabled}"

    if current_config is None:
        current_config = read_running_config(net_connect)

    current_enabled = current_config.get("lldp_enabled")
    if current_enabled is not None and bool(current_enabled) == bool(enabled):
        logger.info("LLDP already %s, skipping.", "enabled" if enabled else "disabled")
        collector.add_step(
            name=configure_lldp.__name__,
            step_result={
                "changed": False,
                "msg": f"LLDP already {'enabled' if enabled else 'disabled'}, skipping.",
                "commands": [],
                "commands_sent": [],
            },
        )
        return

    if check_mode:
        logger.info("Check mode: %s", msg)
    else:
        logger.info("%s", msg)
        send_command(net_connect, cmd=cmd)
    collector.add_step(
        name=configure_lldp.__name__,
        step_result={
            "changed": True,
            "msg": msg,
            "commands": [cmd],
            "commands_sent": [] if check_mode else [cmd],
        },
    )

def run_module(module):
    """Establish connection"""
    device = build_device(module)

    collector = ResultCollector()  # Initialize the ResultCollector
    collector.set_basic_info(
        switch=module.params["host"],
        check_mode=module.check_mode,
        verbosity=module._verbosity,
    )

    system = module.params.get("system") or {}
    dns = module.params.get("dns") or {}
    ntp = module.params.get("ntp") or {}
    lldp = module.params.get("lldp") or {}

    # Only read what the playbook actually asks for. The reads are
    # ``show`` commands: they run in check mode too and never enter config
    # mode, so check mode can tell a matching switch from a differing one.
    need_system_read = any(system.get(key) for key in ("hostname", "location", "contact"))
    need_running_read = bool(
        dns.get("primary")
        or (
            ntp.get("type") == "ntp"
            and ntp.get("ntp_utc")
            and len(ntp.get("ntp_servers") or []) >= 2
            and ntp.get("ntp_fetch_time") is not None
        )
        or lldp.get("enabled") is not None
    )

    with ConnectHandler(**device) as net_connect:
        net_connect.enable()
        current_system = read_system_info(net_connect) if need_system_read else {}
        current_config = read_running_config(net_connect) if need_running_read else {}

        if not module.check_mode:
            net_connect.config_mode()

        set_general_information(
            net_connect, system, collector, module.check_mode, current_system=current_system
        )
        configure_dns(
            net_connect, dns, collector, module.check_mode, current_config=current_config
        )
        configure_ntp(
            net_connect, ntp, collector, module.check_mode, current_config=current_config
        )
        configure_lldp(
            net_connect, lldp, collector, module.check_mode, current_config=current_config
        )
    result = collector.return_info()
    if collector.failed:
        result["msg"] = collector.error
        module.fail_json(**result)
    module.exit_json(**result)

def main():
    """Ansible module argument specification and entry point."""
    module = AnsibleModule(
        argument_spec={
            "host": {"type": "str", "required": True},
            "port": {"type": "int", "default": 22},
            "username": {"type": "str", "required": True},
            "password": {"type": "str", "no_log": True, "default": ""},
            "enable_password": {"type": "str", "no_log": True, "default": ""},
            "read_timeout": {"type": "float", "required": False},
            "system": {
                "type": "dict",
                "required": False,
                "options": {
                    "hostname": {"type": "str", "required": False, "default": None},
                    "location": {"type": "str", "required": False, "default": None},
                    "contact": {"type": "str", "required": False, "default": None},
                },
            },
            "lldp": {
                "type": "dict",
                "required": False,
                "options": {
                    "enabled": {"type": "bool", "required": False, "default": None},
                },
            },
            "dns": {
                "type": "dict",
                "required": False,
                "options": {
                    "primary": {"type": "str", "required": False, "default": None},
                    "secondary": {"type": "str", "required": False, "default": None},
                },
            },
            "ntp": {
                "type": "dict",
                "required": False,
                "options": {
                    "type": {"type": "str", "required": False, "default": None},
                    "ntp_utc": {"type": "str", "required": False, "default": None},
                    "ntp_servers": {
                        "type": "list",
                        "elements": "str",
                        "required": False,
                        "default": [],
                    },
                    "ntp_fetch_time": {
                        "type": "int",
                        "required": False,
                        "default": None,
                    },
                },
            },
        },
        supports_check_mode=True,
    )

    try:
        run_module(module)  # run_module now handles exit_json itself
    except Exception as e:
        module.fail_json(msg=str(e), exception=traceback.format_exc(), check_mode=module.check_mode)


if __name__ == "__main__":
    main()
