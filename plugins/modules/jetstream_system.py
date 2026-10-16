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
  - Supports check mode.
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
  description: Whether any configuration command was sent.
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
from ansible.module_utils.basic import AnsibleModule
from netmiko import ConnectHandler

from ansible_collections.lachlanstone.jetstream.plugins.module_utils.send_command import (
    send_command,
)

from ansible_collections.lachlanstone.jetstream.plugins.module_utils.collector import (
    ResultCollector,
)


# Component: Configure logging for Netmiko
logger = logging.getLogger(name="netmiko")
logger.setLevel(level=logging.DEBUG)
logger.propagate = False
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
# Component: StreamHandler (logger.info debug messages to console)
logging_enabled = True  # Set this to False to disable console logging
if logging_enabled:
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level=logging.INFO)
    stream_handler.setFormatter(fmt=formatter)
    logger.addHandler(hdlr=stream_handler)

def read_system_info(net_connect):
    """Read current system info from the switch via ``show system-info``.

    Returns a dict with any of ``hostname``/``location``/``contact`` that
    could be parsed from the output.  Returns an empty dict when the command
    fails or nothing recognizable is parsed, in which case callers fall back
    to applying the desired config (the current, safe behavior).
    """
    try:
        output = send_command(net_connect, cmd="show system-info")
    except Exception:  # pragma: no cover - defensive; switch may reject the command
        logger.info("Unable to read current system info; applying desired config.")
        return {}

    info = {}
    for line in output.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower().replace(" ", "_")
        value = value.strip()
        if key in ("hostname", "system_name", "name") and value:
            info["hostname"] = value
        elif key in ("location", "system_location") and value:
            info["location"] = value
        elif key in ("contact", "system_contact") and value:
            info["contact"] = value
    return info


def set_general_information(net_connect, system, collector, check_mode=False):
    """Set general information on the switch (hostname, location, contact).

    Args:
        check_mode: When True, report what *would* change without sending
            commands to the device.
    """
    changed = False
    params_to_commands: dict[str, str] = {
        "hostname": "hostname",
        "location": "location",
        "contact": "contact-info",
    }
    commands_sent = []
    current = read_system_info(net_connect) if not check_mode else {}

    for param, cmd_prefix in params_to_commands.items():
        value = system.get(param)
        if not value:
            logger.info("No %s provided, skipping %s configuration.", param, param)
            continue

        if not check_mode and current.get(param) == value:
            logger.info("%s already set to %s, skipping.", param, value)
            continue

        cmd = f"{cmd_prefix} {value}"
        if check_mode:
            logger.info("Check mode: would set %s with command: %s", param, cmd)
        else:
            logger.info("Setting %s with command: %s", param, cmd)
            send_command(net_connect, cmd=cmd)
        commands_sent.append(cmd)
        changed = True

    collector.add_step(
        name=set_general_information.__name__,
        step_result={
            "changed": changed,
            "msg": f"Configured system info: hostname={system.get('hostname')}, location={system.get('location')}, contact={system.get('contact')}" if changed else "No system info provided, nothing to configure",
            "commands": commands_sent,
            "commands_sent": commands_sent,
            "system_info": system,
            "hostname": system.get("hostname"),
            "location": system.get("location"),
            "contact": system.get("contact"),
        },
    )

def configure_dns(net_connect, dns, collector, check_mode=False):
    """Configure DNS servers on the switch.

    Args:
        check_mode: When True, report what *would* change without sending
            commands to the device.
    """
    if not dns:
        return

    if dns.get("secondary") and not dns.get("primary"):
        raise ValueError("DNS configuration requires 'primary' server when 'secondary' is specified.")

    if dns.get("primary"):
        cmd = f"ip dns-address primary {dns.get('primary')}"
        if dns.get("secondary"):
            msg = f"Configuring DNS: primary={dns.get('primary')}, secondary={dns.get('secondary')}"
            cmd += f" secondary {dns.get('secondary')}"
        else:
            msg = f"Configuring DNS: primary={dns.get('primary')}, no secondary provided"
        if check_mode:
            logger.info("Check mode: %s", msg)
        else:
            logger.info("%s", msg)
            send_command(net_connect, cmd=cmd)
        collector.add_step(
            name=configure_dns.__name__,
            step_result={
                "changed": False if check_mode else True,
                "msg": msg,
                "commands": [cmd],
                "commands_sent": [cmd],
            },
        )

def configure_ntp(net_connect, ntp, collector, check_mode=False):
    """Configure NTP on the switch.

    Args:
        check_mode: When True, report what *would* change without sending
            commands to the device.
    """
    if not ntp or not ntp.get("type"):
        return

    if ntp.get("type") != "ntp":
        logger.info("NTP type is '%s' (not 'ntp'), skipping NTP configuration.", ntp.get("type"))
        return

    utc = ntp.get("ntp_utc")
    if not utc:
        raise ValueError("NTP configuration requires 'ntp_utc' (e.g., '+00:00').")

    ntp_servers = ntp.get("ntp_servers") or []
    if len(ntp_servers) < 2:
        raise ValueError(
            f"NTP configuration on TP-Link JetStream CLI requires at least 2 servers in 'ntp_servers' (got {len(ntp_servers)})."
        )

    fetch_time = ntp.get("ntp_fetch_time")
    if fetch_time is None:
        raise ValueError("NTP configuration requires 'ntp_fetch_time' (polling interval in minutes).")

    cmd_parts = [
        "system-time",
        "ntp",
        utc,
        *ntp_servers[:2],
        str(fetch_time),
        *ntp_servers[2:5],
    ]
    cmd = " ".join(cmd_parts)
    if check_mode:
        logger.info("Check mode: would configure NTP: %s", cmd)
    else:
        logger.info("Configuring NTP: %s", cmd)
        send_command(net_connect, cmd=cmd)
    collector.add_step(
        name=configure_ntp.__name__,
        step_result={
                "changed": False if check_mode else True,
                "msg": f"Configuring NTP: servers={ntp_servers}, fetch_time={fetch_time}",
                "commands": [cmd],
                "commands_sent": [cmd],
            },
        )

def configure_lldp(net_connect, lldp, collector, check_mode=False):
    """Configure LLDP on the switch.

    Args:
        check_mode: When True, report what *would* change without sending
            commands to the device.
    """
    if not lldp or lldp.get("enabled") is None:
        logger.info("No LLDP configuration provided, skipping.")
        return

    enabled = lldp.get("enabled")
    cmd = "lldp run" if enabled else "no lldp run"
    msg = f"Configuring LLDP: enabled={enabled}"
    if check_mode:
        logger.info("Check mode: %s", msg)
    else:
        logger.info("%s", msg)
        send_command(net_connect, cmd=cmd)
    collector.add_step(
        name=configure_lldp.__name__,
        step_result={
            "changed": False if check_mode else True,
            "msg": msg,
            "commands": [cmd],
            "commands_sent": [cmd],
        },
    )

def run_module(module):
    """Establish connection"""
    device = {
        "device_type": "tplink_jetstream",
        "host": module.params["host"],
        "port": module.params["port"],
        "username": module.params["username"],
        "password": module.params["password"],
        "secret": module.params["enable_password"],
    }

    collector = ResultCollector()  # Initialize the ResultCollector
    collector.set_basic_info(
        switch=module.params["host"],
        check_mode=module.check_mode,
        verbosity=module._verbosity,
    )

    with ConnectHandler(**device) as net_connect:
        net_connect.enable()
        net_connect.config_mode()
        system = module.params.get("system", {})
        set_general_information(net_connect, system, collector, module.check_mode)
        configure_dns(net_connect, module.params.get("dns", {}), collector, module.check_mode)
        configure_ntp(net_connect, module.params.get("ntp", {}), collector, module.check_mode)
        configure_lldp(net_connect, module.params.get("lldp", {}), collector, module.check_mode)
    result = collector.return_info()
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
        module.fail_json(msg=str(e), exception=e, check_mode=module.check_mode)


if __name__ == "__main__":
    main()
