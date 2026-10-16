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
      - Accepted by the argument specification but not applied by the module yet.
    type: dict
    suboptions:
      type:
        description: NTP mode.
        type: str
      ntp_utc:
        description: UTC offset used for NTP time.
        type: str
      ntp_servers:
        description: List of NTP servers.
        type: list
        elements: str
        default: []
      ntp_fetch_time:
        description: Interval at which the switch fetches time.
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

def set_general_information(net_connect, system, collector):
    """Set general information on the switch (hostname, location, contact)."""
    changed = False
    params_to_commands: dict[str, str] = {
        "hostname": "hostname",
        "location": "location",
        "contact": "contact-info",
    }
    commands_sent = []
    for param, cmd_prefix in params_to_commands.items():
        value = system.get(param)
        if value:
            cmd = f"{cmd_prefix} {value}"
            logger.info("Setting %s with command: %s", param, cmd)
            send_command(net_connect, cmd=cmd)
            commands_sent.append(cmd)
            changed = True
        else:
            logger.info("No %s provided, skipping %s configuration.", param, param)

    collector.add_step(
        name=set_general_information.__name__,
        step_result={
            "changed": changed,
            "msg": f"Configured system info: hostname={system.get('hostname')}, location={system.get('location')}, contact={system.get('contact')}" if changed else "No system info provided, nothing to configure",
            "commands_sent": commands_sent,
            "system_info": system,
            "hostname": system.get("hostname"),
            "location": system.get("location"),
            "contact": system.get("contact"),
        },
    )

def configure_dns(net_connect, dns, collector):
    if dns.get("primary"):
        cmd = f"ip dns-address primary {dns.get('primary')}"
        if dns.get("secondary"):
            msg = f"Configuring DNS: primary={dns.get('primary')}, secondary={dns.get('secondary')}"
            cmd += f" secondary {dns.get('secondary')}"
        else:
            msg = "Configuring DNS: primary={dns.get('primary')}, no secondary provided"
        send_command(net_connect, cmd=cmd)
        collector.add_step(
            name=configure_dns.__name__,
            step_result={
                "changed": True,
                "msg": msg,
                "commands_sent": [cmd],
            },
        )

def configure_ntp(net_connect, ntp, collector):
    utc = ntp.get("ntp_utc")
    ntp_servers = ntp.get("ntp_servers") or []
    fetch_time = ntp.get("ntp_fetch_time")

    if ntp.get("type") == "ntp" and utc and len(ntp_servers) >= 2 and fetch_time is not None:
        cmd_parts = [
            "system-time",
            "ntp",
            utc,
            *ntp_servers[:2],
        ]
        if fetch_time is not None:
            cmd_parts.append(str(fetch_time))
        cmd_parts.extend(ntp_servers[2:5])
        cmd = " ".join(cmd_parts)
        send_command(net_connect, cmd=cmd)
        collector.add_step(
            name=configure_ntp.__name__,
            step_result={
                "changed": True,
                "msg": f"Configuring NTP: servers={ntp_servers}, fetch_time={fetch_time}",
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
        set_general_information(net_connect, system, collector)
        configure_dns(net_connect, module.params.get("dns", {}), collector)
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
